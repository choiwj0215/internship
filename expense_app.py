import streamlit as st
import pandas as pd
import plotly.express as px
import os
from dotenv import load_dotenv
from openai import OpenAI

# -----------------------------------------------------------------------------------
# [보안] Streamlit Secrets를 이용한 API 키 (배포용)
# -----------------------------------------------------------------------------------
if "GITHUB_TOKEN" in st.secrets:
    api_key = st.secrets["GITHUB_TOKEN"]
else:
    st.error("⚠️ API 키가 설정되지 않았습니다. Streamlit Secrets 설정을 확인해주세요.")
    st.stop()

# -----------------------------------------------------------------------------------
# 월간 리포트 마크다운 생성기
# -----------------------------------------------------------------------------------
def generate_monthly_report(df, current_budget, sum_amount, current_budget_diff, 
                            essential_amount, waste_amount, essential_rate, waste_rate, 
                            sat_summary, ai_insights):
    """지표와 AI 피드백을 모아 하나의 마크다운 문서로 합쳐줍니다."""
    budget_status = "여유" if current_budget_diff >= 0 else "초과(적자)"
    
    report = f"""# 📊 가치 소비 기반 월간 재무 리포트

**생성일:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

---

## 💰 1. 핵심 지표 요약

| 항목 | 금액(비율) | 비고 |
| :--- | :--- | :--- |
| **이번 달 목표 예산** | {current_budget:,.0f}원 | - |
| **이번 달 총 지출액** | {sum_amount:,.0f}원 | 예산 대비 {abs(current_budget_diff):,.0f}원 **{budget_status}** |
| **필수 지출** | {essential_amount:,.0f}원 ({essential_rate:.1f}%) | 
| **비필수(선택) 지출** | {waste_amount:,.0f}원 ({waste_rate:.1f}%) | 

**💡 지출 만족도 현황:** {sat_summary}

---

## 🏷️ 2. 카테고리별 지출 현황

| 카테고리 | 지출 금액 | 비중 |
| :--- | :--- | :--- |
"""
    
    if 'category' in df.columns:
        category_sum = df.groupby('category')['amount'].sum().sort_values(ascending=False)
        total = category_sum.sum()
        for cat, amount in category_sum.items():
            percentage = (amount / total * 100) if total > 0 else 0
            report += f"| {cat} | {amount:,.0f}원 | {percentage:.1f}% |\n"
            
    report += """
---

## 💸 3. 금액 상위 5개 지출 내역

| 결제일 | 카테고리 | 결제 내역 | 결제 금액 | 만족도 |
| :--- | :--- | :--- | :--- | :--- |
"""
    
    top5 = df.nlargest(5, 'amount')
    for _, row in top5.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else '-'
        desc = row['description'] if pd.notna(row['description']) else '-'
        sat = f"{int(row['satisfaction'])}점" if ('satisfaction' in df.columns and pd.notna(row['satisfaction'])) else "-"
        report += f"| {date_str} | {row['category']} | {desc} | {row['amount']:,.0f}원 | {sat} |\n"

    if ai_insights:
        report += f"\n---\n\n## 🤖 4. 재무 컨설턴트(AI)의 맞춤형 솔루션\n\n{ai_insights}\n"
    
    return report

# -----------------------------------------------------------------------------------
# 1. 페이지 설정 및 폰트 디자인 
# -----------------------------------------------------------------------------------
st.set_page_config(page_title="지출 분석 대시보드", page_icon="💸", layout="wide")

# [UI 개선] 전체 폰트를 'Pretendard'로 적용하되, 아이콘 폰트는 깨지지 않게 보호
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

* {
    font-family: 'Pretendard', sans-serif;
}

/* 화살표(토글) 등 Streamlit 기본 아이콘 폰트 깨짐 방지 */
.material-symbols-rounded, .material-icons, [class*="icon"] {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}
</style>
""", unsafe_allow_html=True)

st.title('💸 맞춤형 지출 분석 대시보드')
st.markdown('이번 달 지출을 깊이 있게 분석하고, 과거 데이터와 비교하여 다음 달 예산을 계획해보세요.')

# -----------------------------------------------------------------------------------
# 2. 파일 업로드 (Expander 활용)
# -----------------------------------------------------------------------------------
with st.expander("📂 데이터 파일 업로드", expanded=True):
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        uploaders_recent = st.file_uploader(
            '🎯 1. 이번 달 지출 내역 (AI 분석 및 메인 지표용)',
            type=['csv', 'xls', 'xlsx'],
            accept_multiple_files=True 
        )
    with col_up2:
        uploaders_past = st.file_uploader(
            '📅 2. 과거 지출 내역 (월별 추이 차트 비교용 / 선택)',
            type=['csv', 'xls', 'xlsx'],
            accept_multiple_files=True 
        )

# -----------------------------------------------------------------------------------
# 3. 데이터 로드 및 병합 로직
# -----------------------------------------------------------------------------------

# 과거 데이터 처리
df_past = pd.DataFrame()
if uploaders_past:
    all_past = []
    for file in uploaders_past:
        try:
            if file.name.endswith('.csv'):
                temp_past = pd.read_csv(file)
            else:
                temp_past = pd.read_excel(file)
            temp_past.columns = [col.lower() for col in temp_past.columns]
            all_past.append(temp_past)
        except Exception as e:
            st.error(f"{file.name} 과거 파일 오류: {e}")
            
    if all_past:
        df_past = pd.concat(all_past, ignore_index=True)
        df_past['date'] = pd.to_datetime(df_past['date'], format='mixed', errors='coerce')
        df_past['year_month'] = df_past['date'].dt.strftime('%Y-%m')
        
        if df_past['amount'].dtype == 'object':
            df_past['amount'] = df_past['amount'].str.replace(',', '').str.replace('원', '')
        df_past['amount'] = pd.to_numeric(df_past['amount'], errors='coerce').fillna(0).astype(int)
        df_past['category'] = df_past['category'].str.strip()

# 최근 데이터 처리
if uploaders_recent:
    all_dfs = []
    for file in uploaders_recent:
        try:
            if file.name.endswith('.csv'):
                temp_df = pd.read_csv(file)
            else:
                temp_df = pd.read_excel(file)
            temp_df.columns = [col.lower() for col in temp_df.columns]
            all_dfs.append(temp_df)
        except Exception as e:
            st.error(f"{file.name} 파일을 읽는 중 오류가 발생했습니다: {e}")

    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
    else:
        st.stop()
else:
    st.info("👆 분석을 시작하려면 이번 달 지출 내역(1번 칸)을 먼저 업로드하세요.")
    st.stop()

# -----------------------------------------------------------------------------------
# [전처리 1] 결측치(Null) 검증
# -----------------------------------------------------------------------------------
allowed_null_cols = ['description', 'satisfaction']
null_cols = df.columns[df.isnull().any()].tolist()
invalid_null_cols = [col for col in null_cols if col not in allowed_null_cols]

if invalid_null_cols:
    st.error(f"🚨 **데이터 오류:** 다음 컬럼에 빈 값(Null)이 존재합니다 -> **{', '.join(invalid_null_cols)}**\n\n'description'(내역), 'satisfaction'(만족도)을 제외한 모든 필수 데이터는 빠짐없이 입력되어야 합니다.")
    st.stop() 

# -----------------------------------------------------------------------------------
# [전처리 2] 데이터 정제
# -----------------------------------------------------------------------------------
df['date'] = pd.to_datetime(df['date'], format='mixed')
df['year_month'] = df['date'].dt.strftime('%Y-%m') 
df = df.sort_values(by='date')

if df['amount'].dtype == 'object':
    df['amount'] = df['amount'].str.replace(',', '').str.replace('원', '')
df['amount'] = df['amount'].astype(int)

df['category'] = df['category'].str.strip()
df['description'] = df['description'].fillna('-').str.strip()

if 'essential' in df.columns and df['essential'].dtype == 'object':
    df['essential'] = df['essential'].map({'True': True, 'False': False, True: True, False: False})

# -----------------------------------------------------------------------------------
# 사이드바 설정 
# -----------------------------------------------------------------------------------
st.sidebar.header('⚙️ 설정 및 필터')

st.sidebar.subheader("💰 예산 목표 관리")
with st.sidebar.expander("예산 설정", expanded=True):
    current_budget = st.number_input(
        "이번 달 예산 (원)", 
        min_value=0, 
        value=1000000, 
        step=10000, 
        format="%d"
    )

st.sidebar.subheader('🔍 데이터 필터 (이번 달 기준)')

all_months = sorted(df['year_month'].unique())
selected_months = []

with st.sidebar.expander("📅 월(Month) 선택", expanded=True):
    if st.checkbox("이번 달 전체 기간", value=True, key="all_months_check"):
        selected_months = all_months
    else:
        for month in all_months:
            if st.checkbox(month, value=True, key=f"m_{month}"):
                selected_months.append(month)

all_categories = sorted(df['category'].unique())
selected_categories = []

with st.sidebar.expander("📂 카테고리 선택", expanded=False):
    if st.checkbox("전체 카테고리 선택", value=True, key="all_cats_check"):
        selected_categories = all_categories
    else:
        for cat in all_categories:
            if st.checkbox(cat, value=True, key=f"c_{cat}"):
                selected_categories.append(cat)

if selected_months and selected_categories:
    df_filtered = df[
        (df['year_month'].isin(selected_months)) & 
        (df['category'].isin(selected_categories))
    ]
elif not selected_months:
    st.warning("선택된 월이 없습니다! 최소 1개 이상의 월을 선택해주세요.")
    st.stop()
elif not selected_categories:
    st.warning("선택된 카테고리가 없습니다! 최소 1개 이상의 카테고리를 선택해주세요.")
    st.stop()

# -----------------------------------------------------------------------------------
# 4. 집계 및 예산 분석 로직
# -----------------------------------------------------------------------------------
num_months = len(selected_months)
sum_amount = df_filtered['amount'].sum()
avg_monthly_expense = sum_amount / num_months if num_months > 0 else 0
avg_amount = int(df_filtered['amount'].mean()) if not df_filtered.empty else 0

if 'essential' in df_filtered.columns:
    waste_amount = df_filtered[df_filtered['essential'] == False]['amount'].sum()
    essential_amount = df_filtered[df_filtered['essential'] == True]['amount'].sum()
    waste_rate = (waste_amount / sum_amount) * 100 if sum_amount > 0 else 0
    essential_rate = 100 - waste_rate
else:
    waste_amount = 0
    essential_amount = sum_amount
    waste_rate = 0
    essential_rate = 100

max_category = df_filtered.groupby('category')['amount'].sum().idxmax() if not df_filtered.empty else "-"
current_budget_diff = current_budget - sum_amount

# -----------------------------------------------------------------------------------
# 핵심 지표
# -----------------------------------------------------------------------------------
st.subheader("📊 핵심 지표 (이번 달 기준)")
with st.container(border=True):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("이번 달 총 지출액", f"{sum_amount:,}원", delta=f"예산대비 {current_budget_diff:,}원", delta_color="normal")
    col2.metric("월 평균 지출액", f"{int(avg_monthly_expense):,}원")
    col3.metric("비필수(선택) 지출", f"{waste_amount:,}원", 
                delta=f"전체 지출의 {waste_rate:.1f}%", delta_color="inverse")
    col4.metric("최다 지출 카테고리", max_category)

st.markdown("<br>", unsafe_allow_html=True) # 여백 추가

unique_cats = sorted(df_filtered['category'].unique())
colors = px.colors.qualitative.Plotly
cat_color_map = {cat: colors[i % len(colors)] for i, cat in enumerate(unique_cats)}

# -----------------------------------------------------------------------------------
# 5. 차트 시각화 및 AI 연동
# -----------------------------------------------------------------------------------
tab_ai, tab1, tab2, tab3 = st.tabs(["🤖 AI 맞춤 컨설팅", "📊 기본 차트 분석", "⚖️ 가치 소비 분석", "📂 데이터 원본"])

# --- [첫 번째 탭] AI 컨설팅 ---
with tab_ai:
    st.subheader("🤖 AI 재무 비서의 맞춤형 솔루션")

    if st.button("✨ AI 재무 리포트 생성하기", use_container_width=True):
        with st.spinner("AI가 고객님의 지출 패턴과 만족도를 분석하고 있습니다... 🔍"):
            try:
                current_budget_status = "여유" if current_budget_diff >= 0 else "초과(적자)"
                
                sat_summary = "만족도 데이터 없음"
                if 'satisfaction' in df_filtered.columns:
                    sat_df_valid = df_filtered.dropna(subset=['satisfaction'])
                    if not sat_df_valid.empty:
                        avg_sat = sat_df_valid['satisfaction'].mean()
                        sat_counts = sat_df_valid['satisfaction'].value_counts().sort_index()
                        sat_distribution = ", ".join([f"{int(k)}점({v}건)" for k, v in sat_counts.items()])
                        sat_summary = f"평균 {avg_sat:.1f}점 / 분포: {sat_distribution}"

                regret_items_str = "없음"
                value_items_str = "없음"
                
                if 'satisfaction' in df_filtered.columns:
                    sat_df_filtered = df_filtered.dropna(subset=['satisfaction'])
                    
                    regret_df = sat_df_filtered[sat_df_filtered['satisfaction'] <= 2].sort_values(by='amount', ascending=False).head(3)
                    if not regret_df.empty:
                        regret_items_str = ""
                        for _, row in regret_df.iterrows():
                            date_str = row['date'].strftime('%m월 %d일') if pd.notnull(row['date']) else ""
                            regret_items_str += f"\n  - {date_str}: [{row['category']}] {row['description']} ({row['amount']:,}원 / 만족도 {int(row['satisfaction'])}점)"
                            
                    value_df = sat_df_filtered[sat_df_filtered['satisfaction'] >= 4].sort_values(by='amount', ascending=False).head(3)
                    if not value_df.empty:
                        value_items_str = ""
                        for _, row in value_df.iterrows():
                            date_str = row['date'].strftime('%m월 %d일') if pd.notnull(row['date']) else ""
                            value_items_str += f"\n  - {date_str}: [{row['category']}] {row['description']} ({row['amount']:,}원 / 만족도 {int(row['satisfaction'])}점)"

                category_breakdown_str = ""
                if not df_filtered.empty:
                    sum_category = df_filtered.groupby('category')['amount'].sum().reset_index().sort_values(by='amount', ascending=False)
                    for _, row in sum_category.iterrows():
                        category_breakdown_str += f"- {row['category']}: {row['amount']:,}원\n"

                system_prompt = """당신은 고객의 데이터를 예리하게 분석하는 수석 재무 컨설턴트입니다.
[🚨 가독성 핵심 규칙]
1. 문단 안에서 줄글로 길게 나열하지 마세요.
2. 설명할 때는 반드시 글머리 기호(-, ✔️, 📌 등)를 적극 사용하여 짧고 명확하게 끊어서 작성하세요.
3. 중요한 숫자, 카테고리, 내역, 날짜는 **굵은 글씨**로 강조하세요."""

                user_prompt = f"""저의 지출 데이터를 바탕으로 맞춤형 재무 피드백을 작성해주세요.

[📊 나의 지출 데이터 요약]
- 이번 달 예산: {current_budget:,}원
- 이번 달 총 지출액: {sum_amount:,}원 (예산 대비 {abs(current_budget_diff):,}원 {current_budget_status})
- ⚖️ 필수 지출액: {essential_amount:,}원 ({essential_rate:.1f}%)
- ⚖️ 비필수 지출액: {waste_amount:,}원 ({waste_rate:.1f}%)
- 지출 만족도 현황: {sat_summary}
- ✨ 훌륭한 가치 소비 (만족도 4~5점 건들): {value_items_str}
- 📉 아까운 지출 (만족도 1~2점 건들): {regret_items_str}

[🛒 이번 달 카테고리별 지출 현황]
{category_breakdown_str.strip()}

[💯 지출 점수 산정 절대 규칙]
- 점수는 100점 만점이며, **'예산과 지출의 격차(초과율/달성률)'가 점수에 가장 큰 영향(80% 이상)**을 미칩니다.
- 지출이 예산을 초과(적자)했다면 초과한 금액과 비율에 비례하여 점수를 대폭 깎으세요.

[💡 미션: 아래의 흐름을 지켜 작성하되, 문단 내에서 글머리 기호로 읽기 쉽게 구성할 것]

1. 💯 이번 달 지출 점수 및 요약
   - 글의 맨 처음에 **"이번 달 고객님의 지출 점수는 OO점입니다!"**라고 크게 발표하세요.
   - 예산 초과/달성 비율을 가장 크게 반영하여 점수를 매긴 이유를 설명하세요.

2. 🔍 지출 패턴에서 주목할 점 (2~3가지)
   - 제공된 카테고리 현황과 데이터를 바탕으로, 이번 달 나의 소비 습관에서 가장 눈에 띄는 특징을 짚어주세요.

3. 💡 가치 소비 칭찬 및 💔 아까운 지출(건별 핀셋 분석)
   - 먼저 제공된 [✨ 훌륭한 가치 소비] 내역들을 건별로 짚으며, "이 지출은 나를 위한 정말 좋은 선택이었습니다"라고 칭찬하고 지지해 주세요.
   - 이어서 제공된 [📉 아까운 지출] 내역들을 하나하나(건별로, **날짜**를 함께 언급하며) 짚어주세요. 특정 지출을 어떻게 줄이거나 대체할 수 있는지 조언하고, 이를 통해 **당장 다음 달에 총 얼마(예상 절약 금액)**를 절약할 수 있는지 명확한 수치로 제시하세요.

4. 🎯 AI가 제안하는 다음 달 권장 예산안 (카테고리별)
   - 3번의 '예상 절약액'과 '필수 지출액'을 종합적으로 고려하여, 당신이 생각하는 가장 현실적이고 이상적인 **'다음 달 총 권장 예산'**을 먼저 굵은 글씨로 제시하세요.
   - 그리고 그 총 예산에 맞춰 주요 카테고리별 권장 예산액을 구체적으로 분배하여 **반드시 표(Markdown Table) 형태**로 제안해 주세요.
   - 표의 컬럼은 **[카테고리 | 이번 달 지출액 | 다음 달 권장 예산액 | 삭감/유지 사유]** 로 구성하여, 이번 달과 다음 달을 직관적으로 비교할 수 있게 작성하세요.
"""

                client = OpenAI(
                    base_url="https://models.inference.ai.azure.com",
                    api_key=api_key,
                )

                response = client.chat.completions.create(
                    model="gpt-4o", 
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7
                )
                
                ai_content = response.choices[0].message.content

                st.success("✅ 고객님만을 위한 맞춤형 분석이 완료되었습니다!")
                st.markdown(ai_content)

                full_report_md = generate_monthly_report(
                    df_filtered, current_budget, sum_amount, current_budget_diff,
                    essential_amount, waste_amount, essential_rate, waste_rate,
                    sat_summary, ai_content
                )
                
                st.download_button(
                    label="📥 완성된 전체 리포트 다운로드 (.md)",
                    data=full_report_md,
                    file_name=f"월간재무리포트_{pd.Timestamp.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

            except Exception as e:
                st.error("🚨 AI 분석 중 오류가 발생했습니다.")
                st.caption(f"상세 오류 내역: {e}")

# --- [두 번째 탭] 기본 차트 ---
with tab1:
    st.subheader("🛒 카테고리별 분석 (이번 달)")
    if not df_filtered.empty:
        sum_category = df_filtered.groupby('category')['amount'].sum().reset_index().sort_values(by='amount', ascending=False)
        
        c1, c2 = st.columns(2)
        with c1:
            fig_catpie = px.pie(
                sum_category, names='category', values='amount', color='category', 
                title='카테고리 별 지출 비율', hole=0.4, color_discrete_map=cat_color_map, 
                labels={'category': '카테고리', 'amount': '지출 금액'}
            )
            fig_catpie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_catpie, use_container_width=True)
        
        with c2:
            fig_catbar = px.bar(
                sum_category, x='category', y='amount', color='category', text='amount', 
                title='카테고리별 지출 금액 순위', template='simple_white', color_discrete_map=cat_color_map, 
                labels={'category': '카테고리', 'amount': '지출 금액'}
            )
            fig_catbar.update_traces(texttemplate='%{text:,}원', textposition='inside', cliponaxis=False)
            fig_catbar.update_layout(yaxis=dict(tickformat=",")) 
            st.plotly_chart(fig_catbar, use_container_width=True)

        st.subheader("📅 월별 지출 추이")
        trend_frames = [df_filtered[['year_month', 'amount', 'category']]]
        if not df_past.empty:
            if 'category' in df_past.columns and selected_categories:
                past_filtered = df_past[df_past['category'].isin(selected_categories)]
            else:
                past_filtered = df_past
            trend_frames.append(past_filtered[['year_month', 'amount', 'category']])
        
        df_trend_combined = pd.concat(trend_frames)
        sum_monthly_chart = df_trend_combined.groupby('year_month')['amount'].sum().reset_index().sort_values(by='year_month')
        
        if len(sum_monthly_chart) > 1:
            fig_monline = px.line(
                sum_monthly_chart, x='year_month', y='amount', text='amount', markers=True, 
                template='simple_white', title='월별 지출 흐름 (과거 데이터 비교)', labels={'year_month': '월(Month)', 'amount': '지출 금액'}
            )
            fig_monline.update_traces(texttemplate='%{text:,}원', textposition='top center')
            fig_monline.update_layout(yaxis=dict(tickformat=","))
            st.plotly_chart(fig_monline, use_container_width=True)
        else:
            st.info("💡 월별 추이를 보시려면 화면 상단의 '2. 과거 지출 내역' 란에 이전 달의 데이터도 추가해주세요.")
    else:
        st.warning("표시할 데이터가 없습니다.")

# --- [세 번째 탭] 가치 소비 차트 ---
with tab2:
    if 'essential' in df_filtered.columns:
        st.subheader("⚖️ 필수 vs 비필수 지출 분석")
        c3, c4 = st.columns(2)
        with c3:
            sum_essential = df_filtered.groupby('essential')['amount'].sum().reset_index()
            sum_essential['essential_label'] = sum_essential['essential'].map({True: '필수 지출', False: '비필수(선택) 지출'})
            fig_esspie = px.pie(
                sum_essential, names='essential_label', values='amount', title='지출 성격별 비율', 
                color='essential_label', color_discrete_map={'필수 지출': '#87CEEB', '비필수(선택) 지출': '#FF9999'},
                labels={'essential_label': '지출 성격', 'amount': '금액'}
            )
            fig_esspie.update_traces(texttemplate='%{label}<br>%{percent}', textinfo='percent+label')
            st.plotly_chart(fig_esspie, use_container_width=True)
        
        with c4:
            df_filtered['essential_label'] = df_filtered['essential'].map({True: '필수', False: '비필수'})
            category_essential = df_filtered.groupby(['category', 'essential_label'])['amount'].sum().reset_index()
            fig_stack = px.bar(
                category_essential, x='category', y='amount', color='essential_label', title='카테고리별 구성', 
                text='amount', color_discrete_map={'필수': '#87CEEB', '비필수': '#FF9999'}, barmode='stack',
                labels={'category': '카테고리', 'amount': '금액', 'essential_label': '성격'}
            )
            fig_stack.update_traces(texttemplate='%{text:,}', textposition='inside')
            fig_stack.update_layout(yaxis=dict(tickformat=","))
            st.plotly_chart(fig_stack, use_container_width=True)

        st.divider()
        st.subheader("💖 만족도 심층 분석")
        if 'satisfaction' in df_filtered.columns:
            sat_df = df_filtered.dropna(subset=['satisfaction']).copy()
            if not sat_df.empty:
                st.markdown("##### 1️⃣ 후회 비용 시각화")
                sat_df['satisfaction_str'] = sat_df['satisfaction'].astype(int).astype(str)
                satisfaction_order = ['1', '2', '3', '4', '5']
                fig_strip = px.strip(
                    sat_df, x='satisfaction', y='amount', color='satisfaction_str', hover_name='description', 
                    stripmode='overlay', title='지출 건별 만족도 분포',
                    labels={'satisfaction': '만족도(점수)', 'amount': '금액', 'satisfaction_str': '만족도'},
                    category_orders={'satisfaction_str': satisfaction_order} 
                )
                fig_strip.update_layout(xaxis=dict(tickmode='linear', dtick=1), yaxis=dict(tickformat=","))
                fig_strip.update_traces(hovertemplate='금액: %{y:,}원<extra></extra>') 
                st.plotly_chart(fig_strip, use_container_width=True)

                st.markdown("##### 2️⃣ 카테고리별 불만족 집중 구역")
                fig_heat = px.density_heatmap(
                    sat_df, x='satisfaction', y='category', z='amount', histfunc='sum', 
                    title='카테고리 x 만족도 지출 히트맵', color_continuous_scale='Reds',
                    labels={'satisfaction': '만족도(점수)', 'category': '카테고리', 'amount': '총 지출액'}
                )
                fig_heat.update_layout(xaxis=dict(tickmode='linear', dtick=1), coloraxis_colorbar=dict(title="총 지출액", tickformat=","))
                fig_heat.update_traces(texttemplate='%{z:,.0f}원')
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.warning("만족도 데이터가 비어있습니다.")
        else:
            st.info("데이터에 'satisfaction' 컬럼이 없습니다.")
    else:
        st.info("데이터에 'essential' 컬럼이 없어 분석할 수 없습니다.")

# --- [네 번째 탭] 원본 데이터 ---
with tab3:
    display_cols = ['date', 'category', 'description', 'amount', 'fixed', 'essential', 'satisfaction']
    final_cols = [c for c in display_cols if c in df_filtered.columns]
    display_df = df_filtered[final_cols].copy()
    if 'date' in display_df.columns:
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        
    st.dataframe(
        display_df, 
        use_container_width=True, 
        hide_index=True, 
        column_config={
            "amount": st.column_config.NumberColumn("결제 금액", format="%d원"),
            "satisfaction": st.column_config.NumberColumn("만족도", format="%d점")
        }
    )