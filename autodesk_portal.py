import streamlit as st
from datetime import datetime

# Page configuration for Autodesk Brand Look
st.set_page_config(page_title="Autodesk Platform - IFM Survey Console Portal", layout="wide")

# Theme setup (Autodesk Black/Yellow)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 15px;
    }
    
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #FFFFFF !important;
    }
    
    .card {
        background-color: #121212;
        border: 1px solid #333333;
        border-left: 4px solid #FFFF00;
        padding: 20px;
        border-radius: 4px;
        margin-bottom: 16px;
        transition: all 0.2s ease;
    }
    .card:hover {
        border-color: #FFFF00;
        background-color: #1a1a1a;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 0px !important;
        border: none !important;
        background-color: transparent !important;
        padding: 0px !important;
        box-shadow: none !important;
    }
    
    div.stButton > button {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: 1px solid #666666 !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        padding: 8px 20px !important;
        transition: all 0.15s ease;
    }
    div.stButton > button:hover {
        border-color: #FFFF00 !important;
        color: #FFFF00 !important;
    }
    
    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    </style>
    """,
    unsafe_allow_html=True
)

# Header
stacked_logo_svg = '<svg width="220" height="85" viewBox="0 0 220 85" fill="none" xmlns="http://www.w3.org/2000/svg"><g transform="scale(2.4) translate(30, 1)"><path d="M0.538536 22.7316L19.9163 10.678H29.9686C30.2781 10.678 30.5561 10.9259 30.5561 11.2662C30.5561 11.5442 30.4321 11.6681 30.2781 11.7605L20.7598 17.4657C20.1416 17.8368 19.9252 18.579 19.9252 19.1356L19.9155 22.7316H32.0097V1.83296C32.0097 1.4303 31.7002 1.09078 31.2367 1.09078H19.6999L0.369995 13.091V22.7316L0.538536 22.7316Z" fill="white"/></g><text x="110" y="74" fill="white" font-family="\'Inter\', sans-serif" font-size="18" font-weight="900" letter-spacing="4.5" text-anchor="middle">AUTODESK</text></svg>'
header_html = f'<div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-top: 10px; margin-bottom: 10px; gap: 20px;"><div style="width: 220px; display: flex; align-items: center;">{stacked_logo_svg}</div><div style="text-align: right; min-width: 250px;"><div style="font-size: 0.75rem; color: #FFFF00; letter-spacing: 0.15em; text-transform: uppercase; font-weight: 600; margin-bottom: 2px;">Informed Design & Factory Management</div><div style="font-size: 1.7rem; font-weight: 700; color: #FFFFFF; letter-spacing: -0.03em;">IFM 総合案内コンソール</div></div></div>'
st.markdown(header_html, unsafe_allow_html=True)
st.markdown("<hr style='border-color:#666666; margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

# Main layout split
col_main, col_sidebar = st.columns([7, 3])

with col_main:
    # 1. 趣旨説明
    st.markdown("###  アセスメント全体の目的と趣旨")
    st.markdown(
        """
        本アセスメントシステムは、工場建設および生産ライン設計におけるデジタル活用成熟度を「As-Is（現状）」と「To-Be（理想）」の2軸で定量可視化し、
        顧客のボトルネック（最大の課題領域）に対して最適な Autodesk ソリューション（Revit, Inventor, Navisworks, ACC, Tandem 等）を提案するための営業・営業技術統合ポータルです。
        
        **分析される2つの主要部門:**
        - **生産技術部門 (PE)**: 工程レイアウト、ライン設計、検証、設備施工、運用保全
        - **工場建築・建設部門 (FI)**: 建物空間計画、BIM設計、干渉チェック、建築施工、FM（建物管理）
        """
    )
    st.markdown("---")

    # 2. リンクと機能説明
    st.markdown("###  各種フォーム・ダッシュボードへのリンク")
    
    # Card 1: 設問回答画面
    st.markdown(
        """
        <div class="card">
            <h4> 設備管理成熟度アセスメント回答画面 (Client Facing)</h4>
            <p>顧客企業の担当者が実際に10の設問に回答し、As-Is / To-Be を選択する公開用フォームです。</p>
            <a href="/?brand=autodesk" target="_blank" style="color:#FFFF00; font-weight:600; text-decoration:none;"> 回答画面を開く (既定デフォルトID)</a>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Card 2: 営業管理画面 (アンケート発行)
    st.markdown(
        """
        <div class="card">
            <h4> 営業担当用 カスタムアンケート発行管理 (Sales Console)</h4>
            <p>特定の顧客企業（例: トヨタ自動車様）専用のアンケートIDを発行し、設問セット（工場設計 / 建築BIM 等）をカスタマイズする管理機能です。</p>
            <a href="/?brand=autodesk&tab=admin" target="_blank" style="color:#FFFF00; font-weight:600; text-decoration:none;"> 営業管理画面へ遷移する</a>
            <span style="font-size:0.8rem; color:#888888; margin-left:15px;">※要パスワード。紛失時は試作管理者に確認してください。</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Card 3: 分析ダッシュボード
    st.markdown(
        """
        <div class="card">
            <h4> 成熟度アセスメント 結果分析ダッシュボード (Maturity Dashboard)</h4>
            <p>送信された回答データを部門別・役職別に集計し、現場層と意思決定層の『認識乖離（Gap）』や、最大課題に対する『AI推奨セールストーク』を出力します。</p>
            <a href="/?brand=autodesk&tab=dashboard" target="_blank" style="color:#FFFF00; font-weight:600; text-decoration:none;"> 分析ダッシュボードを開く</a>
            <span style="font-size:0.8rem; color:#888888; margin-left:15px;">※要パスワード。紛失時は試作管理者に確認してください。</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Card 4: 超管理者メンテナンス ＆ 製品紐付け (Super Admin)
    st.markdown(
        """
        <div class="card">
            <h4> 超管理者用システムメンテナンス ＆ 製品紐付け (Super Admin Console)</h4>
            <p>DBデータのクレンジング（削除）、および各設問がどのAutodesk製品の提案シナリオに結びついているかの「Autodesk製品提案マッピング」を閲覧できます。</p>
            <a href="/?brand=autodesk&app=super_admin" target="_blank" style="color:#FFFF00; font-weight:600; text-decoration:none;"> 超管理者コンソールを開く</a>
            <span style="font-size:0.8rem; color:#888888; margin-left:15px;">※要パスワード。紛失時は試作管理者に確認してください。</span>
        </div>
        """,
        unsafe_allow_html=True
    )

with col_sidebar:
    # 3. 使い方フロー (Workflow)
    st.markdown("###  標準運用フロー")
    st.markdown(
        """
        **1. 専用アンケートIDの発行**
        営業管理画面で顧客用のアンケートID（例: `clientname-2026`）を発行。
        
        **2. 顧客へURLを送付**
        以下のクエリ付きURLをコピーして顧客に送付・回答を依頼します。
        `/?brand=autodesk&survey_id=clientname-2026`
        
        **3. 顧客の回答完了**
        顧客が回答を入力・完了すると、自動的に Firestore / Google Sheets にデータが同期されます。
        
        **4. 提案シナリオの確認**
        結果分析ダッシュボードを開き、最大課題（Gap）と推奨プロダクトのセールス方針を確認して商談に臨みます。
        """
    )
    
    st.markdown("---")
    
    # 4. 問い合わせ導線とパスワードポリシー
    st.markdown("###  問い合わせ ＆ 認証について")
    st.info(
        "** パスワードについて**\n\n"
        "各種管理画面・ダッシュボードの閲覧には専用パスワードが必要です。セキュリティ上、コードや共有ドキュメント内にはパスワードを直書きしていません。\n\n"
        "パスワードの発行・確認やシステムエラーに関するご相談は、以下へ直接お問い合わせください：\n\n"
        "**試作管理者 / システムオーナー:**\n"
        " **Hidenari Sasaki / IFMチーム**"
    )
    
    st.markdown("---")
    
    # 5. FAQ
    st.markdown("###  よくある質問 (FAQ)")
    with st.expander("Q. 送信されたデータはどこに保存されますか？"):
        st.write("Google Cloud Firestore に安全に格納され、同時に指定の営業管理用 Google Sheets にもリアルタイム転送されます。")
    with st.expander("Q. 顧客が回答中にエラーが出ると言った場合は？"):
        st.write("メールアドレスの形式チェック（半角英数字、@記号の有無）および個人情報保護方針への同意チェックが正しく入力されているか確認してください。")
