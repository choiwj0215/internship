import streamlit as st
import pandas as pd
import plotly.express as px

# -----------------------------------------------------------------------------------
# 1. 페이지 설정 및 타이틀
# -----------------------------------------------------------------------------------
st.set_page_config(page_title="지출 분석 대시보드", page_icon="💸", layout="wide")

st.title('💸 지출 분석 대시보드')
st.text('여러분의 지출 내역을 업로드하면 상세하게 분석해드립니다.')

# -----------------------------------------------------------------------------------
# 2. 파일 업로드
# -----------------------------------------------------------------------------------
uploader = st.file_uploader(
    '지출 내역 파일(csv, xls, xlsx)을 업로드해주세요',
    type=['csv', 'xls', 'xlsx']
)

# -----------------------------------------------------------------------------------
# 3. 데이터 로드 및 전처리 로직
# -----------------------------------------------------------------------------------
if uploader is not None:
    # (1) 데이터 읽기
    try:
        if uploader.name.endswith('.csv'):
            df = pd.read_csv(uploader)
        else:
            df = pd.read_excel(uploader)
            
        # 컬럼명 소문자 변환 (Date -> date, Amount -> amount 등 호환성 확보)
        df.columns = [col.lower() for col in df.columns]
        
    except Exception as e:
        st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        st.stop()

    # (2) 전처리 코드 (작성해주신 코드 적용)
    
    # --- Date 컬럼 ---
    # date 타입 맞추기 (mixed format 지원)
    df['date'] = pd.to_datetime(df['date'], format='mixed')
    
    # month 컬럼 만들기 (str) - 정렬을 위해 01, 02 형태가 좋지만 원본 유지
    df['month'] = df['date'].dt.month.astype(str)
    
    # year_month 컬럼 (분석용)
    df['year_month'] = df['date'].dt.strftime('%Y-%m')

    # --- Amount 컬럼 ---
    # 콤마, 원 제거 및 int 변환
    if df['amount'].dtype == 'object':
        df['amount'] = df['amount'].str.replace(',', '').str.replace('원', '')
    df['amount'] = df['amount'].astype(int)

    # --- Category 컬럼 ---
    df['category'] = df['category'].str.strip()

    # --- Description 컬럼 ---
    df['description'] = df['description'].fillna('-')
    df['description'] = df['description'].str.strip()
    
    # --- Essential 컬럼 처리 (만약 문자열로 들어올 경우 대비) ---
    if 'essential' in df.columns and df['essential'].dtype == 'object':
        df['essential'] = df['essential'].map({'True': True, 'False': False, True: True, False: False})

    # 사이드바 필터 
    # -----------------------------------------------------------------------------------
    st.sidebar.header('🔍 필터 옵션')

    # (1) 월(Month) 목록 추출
    all_months = sorted(df['year_month'].unique())

    # (2) 사이드바 멀티 셀렉트 박스 생성
    selected_months = st.sidebar.multiselect(
        '확인하고 싶은 월을 선택하세요',
        all_months,
        default=all_months  # 기본값: 전체 선택
    )

    # (3) 데이터 필터링 적용 
    if selected_months:
        df = df[df['year_month'].isin(selected_months)]
    else:
        st.warning("선택된 월이 없습니다! 월을 선택해주세요.")
        st.stop() # 선택된 게 없으면 아래 코드 실행 중단

    # -----------------------------------------------------------------------------------
    # 4. 집계 (Metrics)
    # -----------------------------------------------------------------------------------
    
    # 1. 총 지출
    sum_amount = df['amount'].sum()
    
    # 2. 건당 평균
    avg_amount = int(df['amount'].mean())
    
    # 3. 비필수 지출(낭비) 계산
    if 'essential' in df.columns:
        waste_amount = df[df['essential'] == False]['amount'].sum()
        waste_rate = (waste_amount / sum_amount) * 100 if sum_amount > 0 else 0
    else:
        waste_amount = 0
        waste_rate = 0

    # 4. 최대 지출 카테고리/항목
    max_category = df.groupby('category')['amount'].sum().idxmax()
    max_description = df.groupby('description')['amount'].sum().idxmax()

    # --- 메인 지표 표시 (Metric) ---
    st.divider()
    st.subheader("📊 핵심 지표")
    
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("총 지출 금액", f"{sum_amount:,}원")
    col2.metric("건당 평균 지출", f"{avg_amount:,}원")
    
    # 낭비율은 빨간색/초록색으로 표시하기 위해 delta 활용 (낮을수록 좋음)
    col3.metric("비필수 지출 (낭비)", f"{waste_amount:,}원", 
                delta=f"총 지출의 {waste_rate:.1f}%", delta_color="inverse")
    
    col4.metric("최다 지출 카테고리", max_category)

    st.divider()

    # -----------------------------------------------------------------------------------
    # 5. 차트 시각화
    # -----------------------------------------------------------------------------------
    
    # Row 1: 카테고리 분석 (파이차트 & 바차트)
    st.subheader("🛒 카테고리별 분석")
    
    sum_category = df.groupby('category')['amount'].sum().reset_index()
    sum_category = sum_category.sort_values(by='amount', ascending=False)
    
    c1, c2 = st.columns(2)
    
    with c1:
        # 카테고리 별 지출 비율 (파이 차트)
        fig_catpie = px.pie(sum_category,
                            names='category',
                            values='amount',
                            title='카테고리 별 지출 비율',
                            hole=0.4)
        fig_catpie.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_catpie, use_container_width=True)
        
    with c2:
        # 카테고리 별 지출 금액 비교 (바 차트)
        fig_catbar = px.bar(sum_category,
                            x='category',
                            y='amount',
                            color='category',
                            text='amount',
                            title='카테고리별 지출 금액 순위',
                            template='simple_white')

        fig_catbar.update_traces(texttemplate='%{text:,}원',
                                 textposition='inside',
                                 cliponaxis=False)
        st.plotly_chart(fig_catbar, use_container_width=True)

    # Row 2: 월별 추이
    st.subheader("📅 월별 지출 추이")
    
    # 월별 정렬을 위해 숫자형 컬럼 임시 생성
    sum_monthly = df.groupby('year_month')['amount'].sum().reset_index() # year_month 기준이 더 정확함
    sum_monthly = sum_monthly.sort_values(by='year_month')

    fig_monline = px.line(sum_monthly,
                          x='year_month',
                          y='amount',
                          text='amount',
                          markers=True,
                          template='simple_white',
                          title='월별 지출 흐름')

    fig_monline.update_traces(texttemplate='%{text:,}원', textposition='top center')
    st.plotly_chart(fig_monline, use_container_width=True)

    # Row 3: 필수/비필수 분석
    if 'essential' in df.columns:
        st.subheader("⚖️ 가치 소비 분석 (필수 vs 선택)")
        
        c3, c4 = st.columns(2)
        
        with c3:
            # 필수/선택 지출 비율 (파이 차트)
            sum_essential = df.groupby('essential')['amount'].sum().reset_index()
            sum_essential['essential_label'] = sum_essential['essential'].map({True: '필수 지출', False: '비필수 지출(낭비)'})

            fig_esspie = px.pie(sum_essential,
                                names='essential_label',
                                values='amount',
                                title='지출 성격별 비율',
                                color='essential_label',
                                color_discrete_map={'필수 지출': '#87CEEB', '비필수 지출(낭비)': '#FF9999'})

            fig_esspie.update_traces(texttemplate='%{label}<br>%{percent}', textinfo='percent+label')
            st.plotly_chart(fig_esspie, use_container_width=True)

        with c4:
            # 카테고리 내부의 "필수 vs 선택" 비중 (스택 바 차트)
            df['essential_label'] = df['essential'].map({True: '필수', False: '선택'})
            category_essential = df.groupby(['category', 'essential_label'])['amount'].sum().reset_index()
            
            fig_stack = px.bar(category_essential,
                               x='category',
                               y='amount',
                               color='essential_label',
                               title='카테고리별 필수/선택 지출 구성',
                               text='amount',
                               color_discrete_map={'필수': '#87CEEB', '선택': '#FF9999'},
                               barmode='stack') # 스택 모드
            
            fig_stack.update_traces(texttemplate='%{text:,}', textposition='inside')
            st.plotly_chart(fig_stack, use_container_width=True)

    # 원본 데이터 확인하기
    with st.expander("📂 원본 데이터 미리보기"):
        # 1. 보여줄 컬럼 목록 정의 
        display_columns = [
            'date', 'category', 'description', 'amount', 
            'fixed', 'essential', 'satisfaction'
        ]
        
        # 2. 실제로 존재하는 컬럼만 필터링 
        final_columns = [col for col in display_columns if col in df.columns]
        
        # 3. 날짜 포맷 변경 (YYYY-MM-DD)해서 보여주기
        # (원본 df를 건드리지 않기 위해 .copy() 사용)
        display_df = df[final_columns].copy()
        
        # 날짜가 datetime 객체면 문자열로 바꿔서 깔끔하게 출력
        if 'date' in display_df.columns:
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')

        # 4. 화면에 출력
        st.dataframe(display_df, use_container_width=True)

else:
    st.info("👆 위 버튼을 눌러 파일을 업로드하면 분석 결과가 나타납니다.")