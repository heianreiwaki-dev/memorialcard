import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps, ImageFilter
import io
import os
import base64

# ==========================================
# 🚨 最新版Streamlitエラー回避パッチ
# ==========================================
import streamlit.elements.image as st_image
import streamlit.elements.lib.image_utils as image_utils
if not hasattr(st_image, "image_to_url"):
    st_image.image_to_url = image_utils.image_to_url
class FakeLayoutConfig:
    def __init__(self, width):
        self.width = width
        self.use_container_width = False
original_image_to_url = st_image.image_to_url
def patched_image_to_url(image, width_or_config, *args, **kwargs):
    if isinstance(width_or_config, (int, float)):
        width_or_config = FakeLayoutConfig(int(width_or_config))
    return original_image_to_url(image, width_or_config, *args, **kwargs)
st_image.image_to_url = patched_image_to_url
image_utils.image_to_url = patched_image_to_url

# --- 1. 定数定義 ---
PAPER_SIZES = {
    "2L版 (127x178mm)": (600, 840),
    "L版 (89x127mm)": (420, 600),
    "ハガキ (100x148mm)": (472, 700),
    "A4 (210x297mm)": (700, 990),
}
FRAME_FILES = {"枠なし": None, "枠1 (シンプル)": "waku.png", "枠2 (装飾)": "waku2.png"}
PRESET_BG_COLORS = {"ホワイト ⚪": "#FFFFFF", "アイボリー 🍦": "#F5F5F0", "薄いグレー 🔘": "#F0F0F0", "セピア 📜": "#E0D0B0", "ブラック ⚫": "#000000"}
FONTS = {"ゴシック体 (現代的)": "msgothic.ttc", "明朝体 (厳か)": "msmincho.ttc"}

st.set_page_config(page_title="プロ・メモリアルエディタ", layout="wide")

# --- 2. サイドバー ---
with st.sidebar:
    st.header("📋 基本設定")
    selected_size = st.selectbox("出力サイズ", list(PAPER_SIZES.keys()))
    W, H = PAPER_SIZES[selected_size]
    selected_frame_key = st.radio("装飾枠の選択", list(FRAME_FILES.keys()))
    frame_path = FRAME_FILES[selected_frame_key]
    bg_preset = st.selectbox("背景色プリセット", list(PRESET_BG_COLORS.keys()))
    bg_color = PRESET_BG_COLORS[bg_preset]
    
    st.header("📸 写真の設定")
    uploaded_file = st.file_uploader("写真をアップロード", type=["jpg", "png", "jpeg"])
    
    st.header("✍️ 文字の設定")
    user_text = st.text_area("本文", value="")
    selected_font_name = st.selectbox("フォント", list(FONTS.keys()))
    text_size = st.slider("サイズ", 10, 100, 40)

# --- 3. 画像生成ロジック ---
def get_image_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# 台紙と枠の合成
base_paper = Image.new("RGBA", (int(W), int(H)), bg_color)
if frame_path:
    full_frame_path = os.path.join(os.path.dirname(__file__), frame_path)
    if os.path.exists(full_frame_path):
        waku = Image.open(full_frame_path).convert("RGBA").resize((int(W), int(H)))
        base_paper = Image.alpha_composite(base_paper, waku)
    else:
        st.sidebar.error(f"⚠️ {frame_path} が見つかりません")

# 配置オブジェクト
objects_list = []
if uploaded_file:
    p_img = Image.open(uploaded_file).convert("RGBA")
    p_img = ImageOps.contain(p_img, (int(W*0.8), int(H*0.6)))
    objects_list.append({
        "type": "image", "src": f"data:image/png;base64,{get_image_base64(p_img)}",
        "left": int((W-p_img.width)//2), "top": 100
    })

# --- 4. メイン描画 ---
st.title("📱 メモリアルフォト＆メッセージ")

# 💡 鍵の名前を工夫して強制リフレッシュ
clean_bg = bg_color.replace('#', '')
c_key = f"canvas_v21_{clean_bg}_{selected_frame_key}_{selected_size}"

canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 0)",
    background_image=base_paper,
    initial_drawing={"objects": objects_list} if objects_list else None,
    height=int(H), width=int(W),
    drawing_mode="transform", key=c_key,
)

# 💡 デバッグ用：キャンバスの下に現在の合成画像をそのまま表示
st.write("---")
st.write("🖼️ 現在のデザイン（プレビュー）")
st.image(base_paper, caption="背景と枠の合成状態", width=300)