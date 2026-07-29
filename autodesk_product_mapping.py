import streamlit as st
import json
import re
import pandas as pd
from pathlib import Path

# Page config
st.set_page_config(page_title="設問×Autodesk製品マッピング & AI語彙調整", layout="wide")

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_JSON = SCRIPT_DIR / "data" / "ifm_questions.json"

# Theme setup (Autodesk Black/Yellow/White modern dark theme)
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
    
    .mapping-card {
        background-color: #121212;
        border: 1px solid #333333;
        border-left: 5px solid #FFFF00;
        padding: 20px;
        border-radius: 6px;
        margin-bottom: 18px;
    }
    
    /* Product tags: Yellow background with bold black text */
    .product-tag, .product-tag * {
        display: inline-block;
        background-color: #FFFF00 !important;
        color: #000000 !important;
        font-size: 0.82rem !important;
        font-weight: 800 !important;
        padding: 4px 12px;
        border-radius: 14px;
        margin-right: 6px;
        margin-bottom: 6px;
        letter-spacing: 0.02em;
    }
    
    .prompt-box {
        background-color: #121212;
        border: 1px solid #333333;
        border-radius: 6px;
        padding: 16px;
        margin-top: 10px;
    }
    
    .diff-before {
        background-color: #2a1212;
        border-left: 4px solid #ff4d4d;
        padding: 12px;
        border-radius: 4px;
        font-size: 0.92rem;
    }
    
    .diff-after {
        background-color: #122a18;
        border-left: 4px solid #4dff88;
        padding: 12px;
        border-radius: 4px;
        font-size: 0.92rem;
    }

    div.stButton > button {
        background-color: #FFFF00 !important;
        color: #000000 !important;
        font-weight: 800 !important;
        border-radius: 4px !important;
        border: none !important;
        font-size: 1.0rem !important;
        padding: 10px 24px !important;
    }
    div.stButton > button:hover {
        background-color: #e6e600 !important;
        color: #000000 !important;
    }
    div.stButton > button * {
        color: #000000 !important;
    }

    header {visibility: hidden; display: none !important;}
    footer {visibility: hidden; display: none !important;}
    #MainMenu {visibility: hidden; display: none !important;}
    </style>
    """,
    unsafe_allow_html=True
)

# Load Questions Data
@st.cache_data
def load_all_questions_json():
    if DATA_JSON.exists():
        with open(DATA_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

questions_db = load_all_questions_json()

# Product Mapping Definitions
PRODUCT_MAPPINGS = {
    "PE01": {"products": ["Autodesk Factory Design Utilities", "Inventor", "Navisworks"], "scenario": "2Dレイアウトから3D設備配置・工程計画への移行", "value": "計画段階での設備干渉回避とライン配置最適化"},
    "PE02": {"products": ["Inventor Professional", "Vault Professional"], "scenario": "属性情報付き3D設計資産管理と設計自動化", "value": "設計変更履歴の一元共有とレイアウト自動生成"},
    "PE03": {"products": ["Navisworks Manage", "Process Analysis"], "scenario": "3D干渉チェックと生産工程シミュレーション", "value": "施工前における設計不整合の100%自動検出"},
    "PE04": {"products": ["Autodesk Construction Cloud (ACC)", "Navisworks 4D"], "scenario": "施工進捗と4Dシミュレーションの連携管理", "value": "現場と設計のリアルタイム同期と展開計画最適化"},
    "PE05": {"products": ["Autodesk Tandem (Digital Twin)", "ACC Ops"], "scenario": "設備保全データと3Dデジタルツインの統合", "value": "予知保全と運用フェーズにおけるデータ活用"},
    
    "FI01": {"products": ["Autodesk Forma", "Revit"], "scenario": "工場建築の空間計画と環境・日照・風向初期シミュレーション", "value": "初期計画段階での建物性能予測と空間最適化"},
    "FI02": {"products": ["Revit Architecture", "Revit MEP"], "scenario": "BIMモデルによる属性付与とサプライヤーLOD連携", "value": "建築・設備データの統合的なBIM設計運用"},
    "FI03": {"products": ["Navisworks Manage", "ACC Model Coordination"], "scenario": "建築・構造・設備(MEP)の統合干渉検証", "value": "手動図面確認の廃止とクラウド統合検証"},
    "FI04": {"products": ["Autodesk Build (ACC)", "BIM 360"], "scenario": "施工現場におけるペーパーレス検査・品質進捗管理", "value": "現場とオフィスをつなぐ一元的な施工管理"},
    "FI05": {"products": ["Autodesk Tandem", "Revit COBie"], "scenario": "BIMデータを維持管理(FM)システムへ引き継ぎ", "value": "竣工データのデジタルツイン化とFMコスト削減"},
    
    "FC01": {"products": ["Autodesk Factory Design Utilities", "AutoCAD Architecture"], "scenario": "2D/3D連動工場レイアウト設計", "value": "DWG資産を活かした3Dファクトリー化"},
    "FC02": {"products": ["Inventor Factory Assets", "Vault"], "scenario": "工場標準設備アセットライブラリの統一管理", "value": "設備再利用率の向上と設計スピード倍増"},
    "FC03": {"products": ["Navisworks", "Process Analysis 360"], "scenario": "工場全体の大型3D点群・モデルの超高速表示・干渉検証", "value": "大規模ラインの事前施工確認とボトルネック解消"},
    "FC04": {"products": ["ACC Docs", "Autodesk Build"], "scenario": "工場建設・改修プロジェクトにおける関係者CDE構築", "value": "協力会社との図面・変更指示のリアルタイム共有"},
    "FC05": {"products": ["Autodesk Tandem", "Factory Digital Twin"], "scenario": "IoT・MESデータと結合したリアルタイム工場モニタリング", "value": "ライン動態の可視化と運用自動化"},

    "AE01": {"products": ["Autodesk Forma", "Revit"], "scenario": "コンセプト建築BIM設計と初期検討", "value": "基本設計の合意形成スピードアップ"},
    "AE02": {"products": ["Revit", "BIM Collaborate Pro"], "scenario": "クラウドマルチユーザー共同設計", "value": "意匠・構造・設備モデルのリアルタイム共同編集"},
    "AE03": {"products": ["Navisworks Manage", "ACC Model Coordination"], "scenario": "施工BIM統合干渉チェック", "value": "手戻り工事の大幅削減"},
    "AE04": {"products": ["Autodesk Build", "Revit Cloud Worksharing"], "scenario": "BIMデータに基づく施工・検査管理", "value": "図面整合性の自動保全と品質確保"},
    "AE05": {"products": ["Autodesk Tandem", "Revit FM Export"], "scenario": "BIM to FM 連携アセット管理", "value": "建物ライフサイクルコストの可視化"},

    "CI01": {"products": ["InfraWorks", "Civil 3D"], "scenario": "広域地形・インフラ初期構想3Dモデル化", "value": "周辺環境を踏まえた迅速な意思決定"},
    "CI02": {"products": ["Civil 3D", "Subassembly Composer"], "scenario": "パラメータ駆動型3D土木詳細設計", "value": "土量計算と道路・敷地設計の自動化"},
    "CI03": {"products": ["Navisworks", "InfraWorks"], "scenario": "地下埋設物・土木構造物の統合干渉検証", "value": "現場手戻りの防止"},
    "CI04": {"products": ["Autodesk Build", "ACC Docs (CDE)"], "scenario": "i-Construction・電子納品データ統合運用", "value": "発注者・施工者間のCDEデータ共有"},
    "CI05": {"products": ["Autodesk Tandem Infrastructure", "Civil 3D Asset Data"], "scenario": "インフラ資産の維持管理デジタルツイン", "value": "長寿命化計画と点検コスト削減"},

    "MF01": {"products": ["Fusion 360", "Inventor Professional"], "scenario": "3D CADによるモデリングとパラメータ設計", "value": "試作回数の削減と開発期間短縮"},
    "MF02": {"products": ["Vault Professional", "Fusion Manage (PLM)"], "scenario": "部品表(BOM)と設計変更(ECO)の自動追跡", "value": "出図ミスゼロと部品再利用の推進"},
    "MF03": {"products": ["Inventor Nastran", "Fusion Simulation"], "scenario": "強度・構造解析およびジェネラティブデザイン", "value": "軽量化と品質・耐久性の両立"},
    "MF04": {"products": ["Fusion CAM", "Inventor CAM"], "scenario": "3軸/5軸NCマシニングプログラムの自動生成", "value": "加工準備時間短縮と高精度加工"},
    "MF05": {"products": ["Fusion Manage", "Autodesk Platform Services (APS)"], "scenario": "サプライチェーンとデータ連携した次世代PLM", "value": "製造プロセスの完全デジタル化"}
}

# Top Bar Header
st.markdown(
    """
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
        <div>
            <div style="font-size:0.85rem; color:#FFFF00; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;">SALES ENGINEERING & AI ASSISTANT</div>
            <h2 style="margin:0; font-weight:700;"> 設問×Autodesk製品マッピング ＆ AI語彙調整アシスタント</h2>
        </div>
        <div>
            <a href="/?brand=autodesk&app=portal" target="_self" style="background-color:#333; color:#FFF; padding:8px 16px; border-radius:4px; text-decoration:none; font-size:0.85rem; font-weight:600;">← ポータル画面へ戻る</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# Module Selector
MODULE_OPTIONS = {
    "IFM 設備管理成熟度 (標準)": "questions",
    "Factory Cloud (工場設計・レイアウト)": "factory_cloud_questions",
    "AEC (建築・設備 BIM)": "aec_questions",
    "Civil (土木・インフラ CIM)": "civil_questions",
    "MFG (製造・プロセス)": "mfg_questions"
}

selected_module_label = st.selectbox(" 対象の専門アセスメントモジュールを選択してください", list(MODULE_OPTIONS.keys()))
selected_module_key = MODULE_OPTIONS[selected_module_label]

# Get questions for selected module
current_questions = questions_db.get(selected_module_key, [])
if "edited_questions" in st.session_state and selected_module_key in st.session_state.edited_questions:
    current_questions = st.session_state.edited_questions[selected_module_key]

tab1, tab2 = st.tabs([" 設問×Autodesk製品マッピング表示", " AI設問語彙調整アシスタント（プロンプト＆一括インポート）"])

# ==================== TAB 1: PRODUCT MAPPING ====================
with tab1:
    st.markdown(f"###  {selected_module_label} の設問・製品提案シナリオ一覧")
    st.caption("各設問の判定レベルと、提案すべきAutodesk主要ソリューション・商談シナリオの対応表です。")
    
    if not current_questions:
        st.warning("指定されたモジュールの設問データが見つかりませんでした。")
    else:
        for idx, q in enumerate(current_questions):
            qid = q.get("question_id", f"Q{idx+1}")
            dept = q.get("department", "")
            phase = q.get("phase", "")
            text = q.get("question_text", "")
            levels = q.get("levels", {})
            
            # Lookup product mapping
            mapping_info = PRODUCT_MAPPINGS.get(qid, {
                "products": ["Autodesk Platform Services", "ACC"],
                "scenario": "デジタル活用プロセスの最適化シナリオ",
                "value": "データ連携による業務効率化と可視化"
            })
            
            with st.container():
                st.markdown(f"""
                <div class="mapping-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-size:1.15rem; font-weight:700; color:#FFFF00;">{qid} 【{dept} / {phase}】</span>
                        <div>
                            {''.join([f'<span class="product-tag">{p}</span>' for p in mapping_info['products']])}
                        </div>
                    </div>
                    <div style="font-weight:600; font-size:1.02rem; margin-bottom:12px; color:#FFFFFF; white-space:pre-wrap; line-height:1.6;">{text}</div>
                    <div style="background-color:#1a1a1a; padding:12px 14px; border-radius:4px; margin-bottom:10px; font-size:0.95rem; border-left:4px solid #FFFF00;">
                        <strong style="color:#FFFFFF;"> 推奨商談シナリオ:</strong> <span style="color:#D5D5CB;">{mapping_info['scenario']}</span><br>
                        <strong style="color:#FFFFFF;"> 顧客提供価値 (Value Prop):</strong> <span style="color:#D5D5CB;">{mapping_info['value']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f" {qid} のレベル1〜5 定義詳細を表示"):
                    for lkey in ["L1", "L2", "L3", "L4", "L5"]:
                        lval = levels.get(lkey, "")
                        st.markdown(f"**{lkey}**: {lval}")

# ==================== TAB 2: AI VOCABULARY ASSISTANT ====================
with tab2:
    st.markdown("###  AIを活用した設問語彙のカスタマイズ＆一括流し込み")
    st.caption("ChatGPT / Claude / Gemini などのAIを使って、商談先企業の業界用語や顧客の理解度に合わせた設問テキストを効率的に生成・反映できます。")
    
    st.markdown("---")
    
    col_ai1, col_ai2 = st.columns([1, 1])
    
    with col_ai1:
        st.markdown("####  ステップ1: AI相談用プロンプト生成ゾーン")
        st.caption("以下のフォームに入力すると、AIが最適なJSON形式で回答を返すプロンプトが自動作成されます。")
        
        target_industry = st.text_input(" ターゲット業界・顧客層", value="半導体クリーンルーム建設・工場設備")
        intent = st.selectbox(
            " 調整の方向性・意図",
            [
                "専門用語を現場目線の作業言葉に平易化する",
                "プラント・設備保全に特化した業界用語に置き換える",
                "建築・施工（BIM/CIM）の標準用語に統一する",
                "L4・L5で『AI・自動化・デジタルツイン』の先進性を強調する",
                "役職者・意思決定層に刺さる経営・成果視点の表現に変更する"
            ]
        )
        custom_instructions = st.text_area(" 追加の細かいこだわり・指示（任意）", value="例: 略語（BIMやCDE）には初出時に簡易注記を入れ、できるだけ親しみやすい日本語にしてください。")
        
        # Build prompt
        sample_q_json = json.dumps(current_questions[:2], ensure_ascii=False, indent=2)
        
        generated_prompt = f"""あなたは製造・建設業およびIT/BIMデジタルトランスフォーメーションに精通したシニアソリューションコンサルタントです。

以下の【対象モジュール】の成熟度アセスメント設問を、指示に従って書き換えてください。

【対象モジュール】: {selected_module_label}
【ターゲット業界・顧客層】: {target_industry}
【調整の方向性】: {intent}
【追加指示】: {custom_instructions}

【出力必須フォーマット】:
必ず以下のJSON配列形式（コードブロック```json ... ```内）のみで出力してください。他の挨拶文や余計な解説は不要です。

```json
[
  {{
    "question_id": "PE01",
    "question_text": "書き換えた設問本文",
    "levels": {{
      "L1": "レベル1定義",
      "L2": "レベル2定義",
      "L3": "レベル3定義",
      "L4": "レベル4定義",
      "L5": "レベル5定義"
    }}
  }}
]
```

【対象の元設問データ】:
{json.dumps(current_questions, ensure_ascii=False, indent=2)}
"""

        st.markdown("** 生成されたAI用指示文（プロンプト）:**")
        st.code(generated_prompt, language="markdown")
        st.info(" 上記コードブロックの右上コピーボタンを押して、ChatGPTやClaude、Geminiにそのまま貼り付けて実行してください。")

    with col_ai2:
        st.markdown("####  ステップ2: AI回答の一括受け止めゾーン")
        st.caption("AIから返ってきた回答テキスト（JSON）をそのまま以下に貼り付けて「取り込み・検証」を押してください。")
        
        ai_response_input = st.text_area(
            " AIの回答テキスト貼り付けエリア",
            height=320,
            placeholder="""```json
[
  {
    "question_id": "PE01",
    "question_text": "...",
    "levels": { ... }
  }
]
```"""
        )
        
        if st.button(" 貼り付け内容を解析して差分プレビュー"):
            if not ai_response_input.strip():
                st.error("AIの回答テキストが入力されていません。")
            else:
                # Extract JSON block
                clean_json_str = ai_response_input
                if "```json" in clean_json_str:
                    clean_json_str = clean_json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json_str:
                    clean_json_str = clean_json_str.split("```")[1].split("```")[0].strip()
                
                try:
                    parsed_qs = json.loads(clean_json_str)
                    if isinstance(parsed_qs, dict) and "questions" in parsed_qs:
                        parsed_qs = parsed_qs["questions"]
                    
                    if not isinstance(parsed_qs, list):
                        st.error("パース失敗: 配列形式のJSON構造ではありません。")
                    else:
                        st.session_state.preview_parsed_qs = parsed_qs
                        st.success(f" パース成功! {len(parsed_qs)} 件の設問データを抽出しました。")
                except Exception as e:
                    st.error(f" パースエラー: JSON構文を確認してください ({str(e)})")

        if "preview_parsed_qs" in st.session_state:
            preview_qs = st.session_state.preview_parsed_qs
            st.markdown("---")
            st.markdown("#####  Before (現行) vs After (AI調整案) 差分比較")
            
            for item in preview_qs:
                qid = item.get("question_id")
                new_text = item.get("question_text", "")
                new_levels = item.get("levels", {})
                
                # find original
                orig_item = next((q for q in current_questions if q.get("question_id") == qid), {})
                orig_text = orig_item.get("question_text", "")
                
                st.markdown(f"**【{qid}】 の変更比較:**")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f'<div class="diff-before"><strong>[Before 現行]</strong><br>{orig_text}</div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f'<div class="diff-after"><strong>[After AI提案]</strong><br>{new_text}</div>', unsafe_allow_html=True)
            
            if st.button(" このAI調整案をアセスメントフォームに一括適用・保存"):
                # Apply changes
                updated_list = []
                parsed_map = {item["question_id"]: item for item in preview_qs if "question_id" in item}
                
                for q in current_questions:
                    qid = q.get("question_id")
                    if qid in parsed_map:
                        new_q = dict(q)
                        if "question_text" in parsed_map[qid]:
                            new_q["question_text"] = parsed_map[qid]["question_text"]
                        if "levels" in parsed_map[qid]:
                            new_q["levels"] = parsed_map[qid]["levels"]
                        updated_list.append(new_q)
                    else:
                        updated_list.append(q)
                
                if "edited_questions" not in st.session_state:
                    st.session_state.edited_questions = {}
                st.session_state.edited_questions[selected_module_key] = updated_list
                
                st.balloons()
                st.success(f" 『{selected_module_label}』 の設問定義にAI語彙調整を一括反映しました！アセスメント回答フォームでテスト可能です。")

st.caption("IFM Product Mapping & AI Assistant | Autodesk Design & Make Solutions")
