import streamlit as st
import pandas as pd
import os

# 1. ページ全体の基本設定
st.set_page_config(
    page_title="Instagram分析アプリ",
    page_icon="📊",
    layout="wide"
)

# 2. アプリのタイトルと使い方ガイド
st.title("📊 Instagram 投稿分析ダッシュボード")
st.markdown("""
### 💡 このアプリの使い方
アカウントの投稿データ（CSV）を読み込み、それぞれの投稿の「いいね数」「保存数」「リーチ数」を分かりやすく分析・表示するツールです。
* **データ確認:** 下の表で、どの投稿が一番人気だったかを確認できます。
* **データの更新:** `sample_data.csv` を書き換えることで、新しい分析データに更新できます。
""")

st.divider()

# 3. CSVデータの読み込みと日本語化
csv_file = 'sample_data.csv'

if os.path.exists(csv_file):
    # CSVの読み込み
    df = pd.read_csv(csv_file)
    
    st.success("✅ CSVデータの読み込みに成功しました！")
    
    # 英語の列名を日本語の列名に変更
    df_display = df.rename(columns={
        'date': '投稿日',
        'caption': 'キャプション（内容）',
        'hashtags': 'ハッシュタグ',
        'likes': 'いいね数',
        'saves': '保存数',
        'reach': 'リーチ数'
    })
    
    # 4. 画面への表示（テーブル）
    st.subheader("📋 投稿データ一覧")
    st.dataframe(df_display, use_container_width=True)
    
else:
    st.error(f"⚠️ データの保存先が見つかりませんでした: {csv_file}")
    st.info("プロジェクトフォルダに `sample_data.csv` が配置されているか確認してください。")