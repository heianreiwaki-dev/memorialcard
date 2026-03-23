import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps, ImageFilter
import io
import os
import base64

# ==========================================
# 🚨 最新版Streamlit(Python 3.14)エラー回避パッチ
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
    # 数値が渡された場合にオブジェクトに変換してエラーを防ぐ
    if isinstance(width_or_config, (int, float)):
        width_or_config = FakeLayoutConfig(int(width_or_config))
    return original_image_to_url(image, width_or_config, *args, **kwargs)

st_image.image_to_url = patched_image_to_url
image_utils.image_to_url = patched_image_to_url
# ==========================================

# --- 1. 定数・サイズ・色定義 ---
PAPER_SIZES = {
    "2L版 (127x178mm)": (600, 840),
    "L版 (89x127mm)": (420, 600),
    "ハガキ (100x148mm)": (472, 700),
    "A4 (210x297mm)": (700, 990),
    "A5 (148x210mm)": (496, 701),
    "B5 (182x257mm)": (610, 860),
}

FRAME_FILES = {
    "枠なし": None,
    "枠1 (シンプル)": "waku.png",
    "枠2 (装飾)": "waku2.png"
}

# 💡 代表的な色の定義（絵文字付きで選びやすく）
PRESET_BG_COLORS = {
    "ホワイト ⚪": "#FFFFFF",
    "アイボリー 🍦": "#F5F5F0",
    "薄いグレー 🔘": "#F0F0F0",
    "セピア 📜": "#E0D0B0",
    "薄ピンク 🌸": "#FFF0F5",
    "薄ブルー 💧": "#F0F8FF",
    "ブラック ⚫": "#000000",
    "カスタム設定 🎨": "CUSTOM"
}

PRESET_TEXT_COLORS = {
    "漆黒 ⚫": "#000000",
    "濃いグレー 🔘": "#333333",
    "ホワイト ⚪": "#FFFFFF",
    "ゴールド風 🟡": "#B8860B",
    "ダークブラウン 🪵": "#3D2B1F",
    "ネイビー 🔵": "#000080",
    "カスタム設定 🎨": "CUSTOM"
}

FONTS = {
    "ゴシック体 (現代的)": "msgothic.ttc",
    "明朝体 (厳か)": "msmincho.ttc"
}

st.set_page_config(page_title="プロ・メモリアルエディタ", layout="wide")

def get_image_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def add_shadow(image, offset=(10, 10), shadow_color=(0, 0, 0, 80)):
    total_width = image.width + abs(offset[0]) + 30
    total_height = image.height + abs(offset[1]) + 30
    back = Image.new("RGBA", (int(total_width), int(total_height)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", image.size, shadow_color)
    back.paste(shadow, (15 + offset[0], 15 + offset[1]))
    back = back.filter(ImageFilter.GaussianBlur(10))
    back.paste(image, (15, 15), image)
    return back

# --- 2. サイドバー設定 ---
with st.sidebar:
    st.header("📋 基本設定")
    selected_size = st.selectbox("出力サイズを選択", list(PAPER_SIZES.keys()), index=0)
    W, H = PAPER_SIZES[selected_size]
    
    selected_frame_key = st.radio("装飾枠の選択", list(FRAME_FILES.keys()))
    frame_path = FRAME_FILES[selected_frame_key]
    
    st.write("🎨 背景色の選択")
    bg_preset = st.selectbox("代表的な背景色", list(PRESET_BG_COLORS.keys()))
    if bg_preset == "カスタム設定 🎨":
        bg_color = st.color_picker("自由に背景色を作る", "#FFFFFF")
    else:
        bg_color = PRESET_BG_COLORS[bg_preset]
    
    # 背景色のプレビュー表示
    st.markdown(f'<div style="width:100%; height:15px; background:{bg_color}; border:1px solid #ccc; border-radius:3px;"></div>', unsafe_allow_html=True)

    st.divider()
    st.header("📸 写真の設定")
    uploaded_file = st.file_uploader("写真をアップロード", type=["jpg", "png", "jpeg"])
    use_shadow = st.toggle("💡 写真に影をつける（立体感）", value=True)
    auto_enhance = st.toggle("✨ オート補正を有効にする", value=True)
    
    st.divider()
    st.header("✍️ 文字の設定")
    user_text = st.text_area("本文 (最大100文字)", value="", placeholder="メッセージを入力してください...", max_chars=100)
    selected_font_name = st.selectbox("フォントの種類", list(FONTS.keys()))
    text_size_init = st.slider("文字の初期サイズ", 10, 150, 45)
    
    st.write("🎨 文字色の選択")
    text_preset = st.selectbox("代表的な文字色", list(PRESET_TEXT_COLORS.keys()))
    if text_preset == "カスタム設定 🎨":
        text_color = st.color_picker("自由に文字色を作る", "#333333")
    else:
        text_color = PRESET_TEXT_COLORS[text_preset]

    st.divider()
    reset_layout = st.button("🔄 配置を初期位置に戻す")

# --- 3. 画像・文字作成エンジン ---
def prepare_image(file, target_w, target_h, is_auto, has_frame, shadow):
    img = Image.open(file).convert("RGBA")
    # 枠がある場合は内側に収める(75%)、ない場合は広めに(90%)
    margin = 0.75 if has_frame else 0.9
    img = ImageOps.contain(img, (int(target_w * margin), int(target_h * (margin - 0.1))))
    if is_auto:
        img = ImageEnhance.Brightness(img).enhance(1.05)
        img = ImageEnhance.Contrast(img).enhance(1.1)
    if shadow:
        img = add_shadow(img)
    return img

def prepare_text_image(text, size, color, target_w, f_path):
    try:
        font = ImageFont.truetype(f_path, size) if os.path.exists(f_path) else ImageFont.load_default()
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

# --- 4. 状態管理 ---
canvas_key = f"final_v14_{uploaded_file.name if uploaded_file else 'none'}_{selected_size}_{selected_frame_key}_{selected_font_name}_{use_shadow}"

if reset_layout:
    st.rerun()

objects_list = []
if uploaded_file:
    p_img = prepare_image(uploaded_file, W, H, auto_enhance, frame_path is not None, use_shadow)
    objects_list.append({
        "type": "image", "src": f"data:image/png;base64,{get_image_base64(p_img)}",
        "left": int((W - p_img.width) // 2), "top": int((int(H * 0.65) - p_img.height) // 2) + (60 if frame_path else 0),
        "scaleX": 1, "scaleY": 1, "angle": 0
    })

if user_text:
    t_img = prepare_text_image(user_text, text_size_init, text_color, W, FONTS[selected_font_name])
    objects_list.append({
        "type": "image", "src": f"data:image/png;base64,{get_image_base64(t_img)}",
        "left": int((W - t_img.width) // 2), "top": int(H * 0.8),
        "scaleX": 1, "scaleY": 1, "angle": 0
    })

# --- 5. メイン画面 ---
st.title("📱 メモリアルフォト＆メッセージ")
st.write(f"現在の設定: **{selected_size}**")

base_paper = Image.new("RGBA", (int(W), int(H)), bg_color)
if frame_path and os.path.exists(frame_path):
    waku = Image.open(frame_path).convert("RGBA").resize((int(W), int(H)))
    base_paper = Image.alpha_composite(base_paper, waku)

canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 0)",
    background_image=base_paper,
    initial_drawing={"objects": objects_list} if objects_list else None,
    height=int(H), width=int(W),
    drawing_mode="transform", display_toolbar=False, key=canvas_key, 
)

# --- 6. 確定と保存 ---
st.divider()
if st.button("✨ デザインを確定してダウンロードの準備をする", use_container_width=True, type="primary"):
    if canvas_result.image_data is not None:
        final_layer = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
        complete_page = Image.alpha_composite(base_paper, final_layer)
        
        st.success("✅ デザインが確定しました。以下のボタンから保存してください。")
        col_d1, col_d2 = st.columns(2)
        
        # JPEG
        buf_jpg = io.BytesIO()
        complete_page.convert("RGB").save(buf_jpg, format="JPEG", quality=95)
        col_d1.download_button("📥 通常保存 (JPEG)", buf_jpg.getvalue(), f"memorial_{selected_size}.jpg", "image/jpeg", use_container_width=True)
        
        # PDF
        buf_pdf = io.BytesIO()
        complete_page.convert("RGB").save(buf_pdf, format="PDF", resolution=100.0)
        col_d2.download_button("📥 高画質印刷用 (PDF)", buf_pdf.getvalue(), f"memorial_{selected_size}.pdf", "application/pdf", use_container_width=True)