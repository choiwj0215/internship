import streamlit as st
import pandas as pd
import plotly.express as px


#타이틀 설정
st.title('💸지출 분석 대시보드')
st.text('여러분의 지출을 분석해드립니다')
st.text('아래에 지출내역을 csv/xlsx/xls 형태로 업로드 해주세요')


#업로드 칸 생성
uploader = st.file_uploader(
        '지출 내역을 업로드해주세요',
        type = ['csv','xls','xlsx']
)