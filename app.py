import streamlit as st
import pandas as pd

st.title("Instagram 分析アプリ")

# CSVファイルの読み込み
try:
    df = pd.read_csv("sample_data.csv")
    st.success("CSVデータの読み込みに成功しました！")
    st.dataframe(df)
except FileNotFoundError:
    st.error("sample_data.csv ファイルが見つかりません。フォルダを確認してください。")
