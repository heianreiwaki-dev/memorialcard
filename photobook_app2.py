import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps, ImageFilter
import io
import os
import base64

# ==========================================
# 🚨 エラー回避パッチ（ここはそのままでOK）
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

# --- 1. 定数・色定義 ---
PAPER_SIZES = {"2L版 (127x178mm)": (600, 840), "L版 (89x127mm)": (420, 600), "ハガキ (100x148mm)": (472, 700), "A4 (210x297mm)": (700, 990)}
FRAME_FILES = {"枠なし": None, "枠1 (シンプル)": "waku.png", "枠2 (装飾)": "waku2.png"}
PRESET_BG_COLORS = {"ホワイト ⚪": "#FFFFFF", "アイボリー 🍦": "#F5F5F0", "薄いグレー 🔘": "#F0F0F0", "セピア 📜": "#E0D0B0", "ブラック ⚫": "#000000"}
PRESET_TEXT_COLORS = {"漆黒 ⚫": "#000000", "濃いグレー 🔘": "#333333", "ホワイト ⚪": "#FFFFFF", "ゴールド風 🟡": "#B8860B", "ダークブラウン 🪵": "#3D2B1F"}
FONTS = {"ゴシック体 (現代的)": "msgothic.ttc", "明朝体 (厳か)": "msmincho.ttc"}

st.set_page_config(page_title="プロ・メモリアルエディタ", layout="wide")

# --- 2. 便利関数 ---
def get_image_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def prepare_text_image(text, size, color, target_w, f_path):
    font_full_path = os.path.join(os.path.dirname(__file__), f_path)
    try:
        font = ImageFont.truetype(font_full_path, size) if os.path.exists(font_full_path) else ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    dummy_img = Image.new("RGBA", (int(target_w), 500))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.multiline_textbbox((0, 0), text, font=font, align="center")
    tw, th = int(bbox[2] - bbox[0] + 60), int(bbox[3] - bbox[1] + 60)
    txt_img = Image.new("RGBA", (max(tw, 100), max(th, 50)), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.multiline_text((tw//2, th//2), text, font=font, fill=color, anchor="mm", align="center")
    return txt_img

# --- 3. サイドバー設定 ---
with st.sidebar:
    st.header("📋 基本設定")
    selected_size = st.selectbox("出力サイズ", list(PAPER_SIZES.keys()))
    W, H = PAPER_SIZES[selected_size]
    selected_frame_key = st.radio("装飾枠の選択", list(FRAME_FILES.keys()))
    frame_path = FRAME_FILES[selected_frame_key]
    bg_preset = st.selectbox("背景色", list(PRESET_BG_COLORS.keys()))
    bg_color = PRESET_BG_COLORS[bg_preset]
    
    st.header("📸 写真の設定")
    uploaded_file = st.file_uploader("写真をアップロード", type=["jpg", "png", "jpeg"])
    
    st.header("✍️ 文字の設定")
    user_text = st.text_area("本文", value="", placeholder="メッセージを入力...")
    selected_font_name = st.selectbox("フォント", list(FONTS.keys()))
    text_size = st.slider("文字のサイズ", 10, 120, 45)
    text_preset = st.selectbox("文字の色", list(PRESET_TEXT_COLORS.keys()))
    text_color = PRESET_TEXT_COLORS[text_preset]
    
    st.divider()
    if st.button("🔄 画面を強制リセット"):
        st.rerun()

# --- 4. 画像生成（背景＋枠） ---
st.title("📱 メモリアルフォト＆メッセージ")

# 台紙と枠を1枚の画像に合成
base_paper = Image.new("RGBA", (int(W), int(H)), bg_color)
if frame_path:
    full_frame_path = os.path.join(os.path.dirname(__file__), frame_path)
    if os.path.exists(full_frame_path):
        waku = Image.open(full_frame_path).convert("RGBA").resize((int(W), int(H)))
        base_paper = Image.alpha_composite(base_paper, waku)

# 初期の配置物リスト作成
objects_list = []
if uploaded_file:
    p_img = Image.open(uploaded_file).convert("RGBA")
    p_img = ImageOps.contain(p_img, (int(W*0.8), int(H*0.6)))
    objects_list.append({
        "type": "image", "src": f"data:image/png;base64,{get_image_base64(p_img)}",
        "left": int((W-p_img.width)//2), "top": 120
    })
if user_text:
    t_img = prepare_text_image(user_text, text_size, text_color, W, FONTS[selected_font_name])
    objects_list.append({
        "type": "image", "src": f"data:image/png;base64,{get_image_base64(t_img)}",
        "left": int((W-t_img.width)//2), "top": int(H*0.75)
    })

# --- 5. キャンバスの鍵（ここが最重要！） ---
# 背景色、枠、サイズ、写真の有無、文字の有無が変わるたびに、鍵（key）を完全に変えます
clean_bg = bg_color.replace('#', '')
c_key = f"canvas_final_{clean_bg}_{selected_frame_key}_{selected_size}_{'y' if uploaded_file else 'n'}_{len(user_text)}"

canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 0)",
    background_image=base_paper,
    initial_drawing={"objects": objects_list} if objects_list else None,
    height=int(H), width=int(W),
    drawing_mode="transform",
    key=c_key, # 👈 この鍵が新しくなると、上の画面が強制的に描き直されます
)

# --- 6. 確定と保存 ---
st.divider()
if st.button("✨ デザインを確定する", use_container_width=True, type="primary"):
    if canvas_result.image_data is not None:
        # キャンバス上の写真や文字を取り出す
        final_layer = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
        # 背景（base_paper）の上に重ねる
        complete_page = Image.alpha_composite(base_paper, final_layer)
        
        st.success("✅ 準備完了！保存ボタンを押してください。")
        c1, c2 = st.columns(2)
        
        buf_j = io.BytesIO()
        complete_page.convert("RGB").save(buf_j, format="JPEG", quality=95)
        c1.download_button("📥 通常保存 (JPEG)", buf_j.getvalue(), "memorial.jpg", "image/jpeg", use_container_width=True)
        
        buf_p = io.BytesIO()
        complete_page.convert("RGB").save(buf_p, format="PDF", resolution=100.0)
        c2.download_button("📥 高画質保存 (PDF)", buf_p.getvalue(), "memorial.pdf", "application/pdf", use_container_width=True)