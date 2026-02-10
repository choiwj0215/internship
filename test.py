# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

# 페이지 설정
st.set_page_config(
    page_title="💰 개인 지출 분석 대시보드",
    page_icon="💰",
    layout="wide"
)

st.title("💰 개인 지출 분석 대시보드")

# 사이드바 - 파일 업로드
with st.sidebar:
    st.header("📁 데이터 업로드")
    uploaded_file = st.file_uploader(
        "CSV 또는 Excel 파일을 업로드하세요",
        type=['csv', 'xlsx', 'xls']
    )

# 메인 영역
if uploaded_file is not None:
    # 파일 타입에 따라 읽기
    try:
        if uploaded_file.name.endswith('.csv'):
            # 인코딩 자동 감지 시도
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)  # 파일 포인터 초기화
                df = pd.read_csv(uploaded_file, encoding='cp949')
        else:
            df = pd.read_excel(uploaded_file)
        
        # 날짜 컬럼 변환
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df['month'] = df['date'].dt.to_period('M').astype(str)
            df['year_month'] = df['date'].dt.strftime('%Y-%m')
        
        st.success(f"✅ 데이터 로드 완료! ({len(df)}건)")
        
        # 데이터 미리보기
        with st.expander("📋 데이터 미리보기"):
            st.dataframe(df.head(10))
        
    except Exception as e:
        st.error(f"파일 읽기 오류: {e}")
        
else:
    st.info("👈 왼쪽 사이드바에서 파일을 업로드해주세요.")
    
    # 샘플 데이터 다운로드 버튼
    st.markdown("---")
    st.markdown("### 📥 샘플 데이터가 필요하신가요?")
    
    # 샘플 데이터 생성
    sample_data = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=30, freq='D'),
        'amount': [15000, 3500, 45000, 12000, 8500, 25000, 6000, 
                   32000, 4500, 18000, 55000, 7500, 21000, 9000,
                   28000, 5500, 16000, 42000, 11000, 8000, 35000,
                   4000, 22000, 13500, 48000, 6500, 19000, 38000,
                   7000, 26000],
        'category': ['식비', '교통비', '쇼핑', '식비', '카페', '문화',
                     '교통비', '식비', '카페', '쇼핑', '의료', '교통비',
                     '식비', '카페', '쇼핑', '교통비', '식비', '문화',
                     '교통비', '카페', '식비', '교통비', '쇼핑', '식비',
                     '문화', '카페', '식비', '쇼핑', '교통비', '식비'],
        'description': ['점심 식사', '지하철', '옷 구매', '저녁 식사', '커피',
                        '영화', '버스', '회식', '아메리카노', '온라인쇼핑',
                        '병원', '택시', '배달음식', '카페라떼', '생필품',
                        '지하철', '편의점', '콘서트', '버스', '디저트',
                        '장보기', '지하철', '신발', '외식', '전시회',
                        '커피', '점심', '악세서리', '택시', '저녁']
    })
    
    csv = sample_data.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 샘플 CSV 다운로드",
        data=csv,
        file_name="sample_expense_data.csv",
        mime="text/csv"
    )