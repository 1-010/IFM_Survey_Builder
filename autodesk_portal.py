import streamlit as st
from datetime import datetime
from pathlib import Path

try:
    SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:
    SCRIPT_DIR = Path(".").resolve()

# Theme setup (Autodesk Black/Yellow/Cyan modern dark theme)
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: Arial, system-ui, -apple-system, "Segoe UI", sans-serif !important;
        font-size: 16px !important;
    }
    
    h1, h2, h3, h4, h5, h6, label, span, p {
        color: #FFFFFF !important;
    }
    
    .card-module {
        background-color: #121212;
        border: 1px solid #333333;
        border-left: 5px solid #FFFF00;
        padding: 22px;
        border-radius: 6px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        transition: all 0.25s ease;
    }
    .card-module:hover {
        border-color: #FFFF00;
        background-color: #1c1c1c;
        transform: translateY(-2px);
    }
    
    .card-tool {
        background-color: #0d1b2a;
        border: 1px solid #1e3a8a;
        border-left: 5px solid #00F0FF;
        padding: 22px;
        border-radius: 6px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,240,255,0.1);
        transition: all 0.25s ease;
    }
    .card-tool:hover {
        border-color: #00F0FF;
        background-color: #13263c;
        transform: translateY(-2px);
    }
    
    .card-admin {
        background-color: #181818;
        border: 1px solid #2e2e2e;
        padding: 14px 18px;
        border-radius: 4px;
        margin-bottom: 10px;
    }
    
    /* Domain badges (Yellow with black text) */
    .badge-domain, .badge-domain * {
        display: inline-block;
        background-color: #FFFF00 !important;
        color: #000000 !important;
        font-size: 0.78rem !important;
        font-weight: 800 !important;
        padding: 3px 10px;
        border-radius: 3px;
        text-transform: uppercase;
        margin-bottom: 8px;
        letter-spacing: 0.05em;
    }
    
    /* Sales & AI Tool badge (Cyan with black text) */
    .badge-tool, .badge-tool * {
        display: inline-block;
        background-color: #00F0FF !important;
        color: #000000 !important;
        font-size: 0.78rem !important;
        font-weight: 800 !important;
        padding: 3px 10px;
        border-radius: 3px;
        text-transform: uppercase;
        margin-bottom: 8px;
        letter-spacing: 0.05em;
    }
    
    .btn-link, .btn-link * {
        display: inline-block;
        margin-top: 10px;
        padding: 8px 18px;
        background-color: #FFFF00 !important;
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        border-radius: 4px;
        text-decoration: none;
        transition: all 0.2s ease;
    }
    .btn-link:hover, .btn-link:hover * {
        background-color: #e6e600 !important;
        color: #000000 !important;
        box-shadow: 0 2px 8px rgba(255,255,0,0.4);
    }
    
    .btn-tool-link, .btn-tool-link * {
        display: inline-block;
        margin-top: 10px;
        padding: 8px 18px;
        background-color: #00F0FF !important;
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        border-radius: 4px;
        text-decoration: none;
        transition: all 0.2s ease;
    }
    .btn-tool-link:hover, .btn-tool-link:hover * {
        background-color: #00cce6 !important;
        color: #000000 !important;
        box-shadow: 0 2px 8px rgba(0,240,255,0.4);
    }
    
    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    </style>
    """,
    unsafe_allow_html=True
)

# Top Header
header_html = '<div style="display:flex;align-items:end;justify-content:space-between;flex-wrap:wrap;margin:12px 0 16px;gap:16px;"><div><div style="font-size:.85rem;color:#FFFF00;letter-spacing:.12em;text-transform:uppercase;font-weight:700;">Informed Design &amp; Factory Management</div><div style="font-size:2.0rem;font-weight:700;color:#FFFFFF;letter-spacing:-.03em;">IFM 総合案内コンソール</div></div><div style="font-size:.85rem;color:#D5D5CB;">for Autodesk Design &amp; Make workflows</div></div>'
st.markdown(header_html, unsafe_allow_html=True)
st.markdown("<hr style='border-color:#444444; margin-top:5px; margin-bottom:24px;'>", unsafe_allow_html=True)

col_main, col_sidebar = st.columns([7, 3])

with col_main:
    # 1. 趣旨説明
    st.markdown("###  アセスメントプラットフォームの概要")
    st.markdown(
        """
        顧客企業のデジタル活用成熟度を「As-Is（現状）」と「To-Be（理想）」の2軸で定量的かつ迅速に診断し、
        最大のボトルネックに対する最適な Autodesk ソリューション（Revit, Inventor, Navisworks, ACC, Tandem, Forma, Civil 3D等）を導き出すアセスメントポータルです。
        """
    )
    st.markdown("---")

    # 2. 専門モジュール別アセスメントフォーム
    st.markdown("###  専門分野別 アセスメント回答フォーム")
    st.caption("対象顧客の業務ドメインに応じた専用フォームを選択してご回答・ご案内いただけます。")
    
    col_m1, col_m2 = st.columns(2)
    
    with col_m1:
        st.markdown(
            """
            <div class="card-module">
                <span class="badge-domain">IFM / 総合・保全</span>
                <h4 style="margin:4px 0 8px; font-weight:700;"> 設備管理成熟度アセスメント (IFM)</h4>
                <p style="font-size:0.92rem; color:#CCCCCC; margin-bottom:12px; min-height:48px;">
                    生産技術（PE）と工場建築（FI）の2軸から、工場全体の設備計画・保全・運用成熟度を総合評価する標準フォーム。
                </p>
                <a href="/?brand=autodesk&app=assessment" class="btn-link">回答フォームを開く →</a>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown(
            """
            <div class="card-module">
                <span class="badge-domain">AEC / 建築・設備</span>
                <h4 style="margin:4px 0 8px; font-weight:700;"> 建築・設備 BIM成熟度アセスメント</h4>
                <p style="font-size:0.92rem; color:#CCCCCC; margin-bottom:12px; min-height:48px;">
                    建物空間計画、BIM設計、LOD連携、施工干渉チェック、FM運用に至る建築・設備BIMの活用度を診断。
                </p>
                <a href="/?brand=autodesk&app=aec" class="btn-link">AECフォームを開く →</a>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <div class="card-module">
                <span class="badge-domain">MFG / 製造・プロダクト</span>
                <h4 style="margin:4px 0 8px; font-weight:700;"> 製造・プロセス成熟度アセスメント</h4>
                <p style="font-size:0.92rem; color:#CCCCCC; margin-bottom:12px; min-height:48px;">
                    製品設計・PDM/PLM、解析検証、製造準備、サプライヤー連携など製造プロセス全体のデジタル成熟度を診断。
                </p>
                <a href="/?brand=autodesk&app=mfg" class="btn-link">MFGフォームを開く →</a>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_m2:
        st.markdown(
            """
            <div class="card-module">
                <span class="badge-domain">Factory Cloud / 工場設計</span>
                <h4 style="margin:4px 0 8px; font-weight:700;"> 工場設計・ファクトリーアセスメント</h4>
                <p style="font-size:0.92rem; color:#CCCCCC; margin-bottom:12px; min-height:48px;">
                    ライン配置、3Dデジタルモックアップ、工程シミュレーション、工場建設・運用の最適化に特化したアセスメント。
                </p>
                <a href="/?brand=autodesk&app=factory" class="btn-link">Factoryフォームを開く →</a>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <div class="card-module">
                <span class="badge-domain">Civil / 土木・インフラ</span>
                <h4 style="margin:4px 0 8px; font-weight:700;"> 土木・インフラ CIM成熟度アセスメント</h4>
                <p style="font-size:0.92rem; color:#CCCCCC; margin-bottom:12px; min-height:48px;">
                    敷地計画、3D土木設計(CIM)、i-Construction、構造解析、CDE（共通データ環境）運用度を診断。
                </p>
                <a href="/?brand=autodesk&app=civil" class="btn-link">Civilフォームを開く →</a>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    # 3. 営業支援 ＆ 設問カスタマイズツール
    st.markdown("###  営業技術・営業ツール")
    st.markdown(
        """
        <div class="card-tool">
            <span class="badge-tool">SALES &amp; AI TOOL</span>
            <h4 style="margin:4px 0 8px; font-weight:700; color:#00F0FF;"> 設問×Autodesk製品マッピング ＆ AI語彙調整アシスタント</h4>
            <p style="font-size:0.95rem; color:#E0E0E0; margin-bottom:14px; line-height:1.6;">
                専門モジュールごとの設問と対応する <strong>Autodesk 製品（Revit, Inventor, Navisworks, ACC, Tandem 等）のマッピング一覧</strong> を閲覧・検索できます。<br>
                さらに、営業担当がChatGPTやClaudeなどのAIを活用して、顧客の業界や商談内容に合わせた<strong>設問語彙の調整プロンプトの生成・AI回答の一括取り込み</strong>を行えます。
            </p>
            <a href="/?brand=autodesk&app=product_mapping" class="btn-tool-link">製品マッピング ＆ AI語彙調整ツールを開く →</a>
            <a href="/?brand=autodesk&app=sales_portal" class="btn-link" style="margin-left:12px;">営業専用マイポータルを開く →</a>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. 管理者・分析リンク
    with st.expander(" 管理・分析・管理者用コンソール（各種設定・集計）"):
        st.caption("※これらの画面は管理・集計担当者用の機能です。閲覧には専用パスワードが必要です。")
        
        st.markdown(
            """
            <div class="card-admin">
                <strong> 営業担当用 カスタムアンケート発行管理 (Sales Console)</strong><br>
                <span style="font-size:0.88rem; color:#AAAAAA;">特定顧客用のアンケートID（例: toyota-2026）の発行・設問選択。</span><br>
                <a href="/?brand=autodesk&tab=admin" style="color:#FFFF00; font-size:0.9rem; font-weight:700;">移動する →</a>
            </div>
            <div class="card-admin">
                <strong> 結果分析ダッシュボード (Maturity Analytics)</strong><br>
                <span style="font-size:0.88rem; color:#AAAAAA;">回答データの集計、部門間Gap分析、AI推奨提案シナリオの確認。</span><br>
                <a href="/?brand=autodesk&tab=dashboard" style="color:#FFFF00; font-size:0.9rem; font-weight:700;">移動する →</a>
            </div>
            <div class="card-admin">
                <strong> 超管理者用システムメンテナンス (Super Admin Console)</strong><br>
                <span style="font-size:0.88rem; color:#AAAAAA;">データベースクレンジング、システム全体の製品紐付けマスタ設定。</span><br>
                <a href="/?brand=autodesk&app=super_admin" style="color:#FFFF00; font-size:0.9rem; font-weight:700;">移動する →</a>
            </div>
            """,
            unsafe_allow_html=True
        )

with col_sidebar:
    hero_path = SCRIPT_DIR / "data" / "images" / "brand-image-prototype-1-dark.webp"
    if hero_path.exists():
        st.image(str(hero_path), caption="設計・製造データをつなぐIFMアセスメント", use_container_width=True)

    st.markdown("###  標準運用フロー")
    st.markdown(
        """
        **1. 専門アセスメントの選択**
        顧客の業種（建設/工場/製造/土木）に応じたフォームまたはポータルURLをコピー。
        
        **2. 専用アンケートID発行（任意）**
        管理画面から顧客固有のID（例: `clientname-2026`）を発行してカスタマイズURLを送付。
        
        **3. AIで語彙を調整**
        商談前に「AI語彙調整アシスタント」で顧客の業界用語に合わせた設問テキストを生成・調整。
        
        **4. 結果分析 ＆ 提案**
        顧客の回答後、分析ダッシュボードでボトルネックと推奨Autodesk製品を確認。
        """
    )
    
    st.markdown("---")

    st.markdown("###  サポート ＆ お問い合わせ")
    st.info(
        "**システム管理者 / 試作オーナー:**\n\n"
        "**Hidenari Sasaki / IFMチーム**\n\n"
        "パスワード照会や機能追加のリクエストは直接管理者へお伝えください。"
    )

st.caption("IFM Maturity Assessmentは独立した試作サービスです。AutodeskおよびAutodesk製品名は識別目的で使用しています。")
