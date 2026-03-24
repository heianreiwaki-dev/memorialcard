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
    if isinstance(width_or_config, (int, float)):
        width_or_config = FakeLayoutConfig(int(width_or_config))
    return original_image_to_url(image, width_or_config, *args, **kwargs)

st_image.image_to_url = patched_image_to_url
image_utils.image_to_url = patched_image_to_url
# ==========================================

# --- 1. 定数・色・フォント定義 ---
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

PRESET_BG_COLORS = {
    "ホワイト ⚪": "#FFFFFF", "アイボリー 🍦": "#F5F5F0", "薄いグレー 🔘": "#F0F0F0",
    "セピア 📜": "#E0D0B0", "ブラック ⚫": "#000000", "カスタム設定 🎨": "CUSTOM"
}

PRESET_TEXT_COLORS = {
    "漆黒 ⚫": "#000000", "濃いグレー 🔘": "#333333", "ホワイト ⚪": "#FFFFFF",
    "ゴールド風 🟡": "#B8860B", "ダークブラウン 🪵": "#3D2B1F", "カスタム設定 🎨": "CUSTOM"
}

# 💡 ネット公開用：GitHubに上げたフォントファイル名を指定
FONTS = {
    "ゴシック体 (現代的)": "msgothic.ttc",
    "明朝体 (厳か)": "msmincho.ttc"
}

st.set_page_config(page_title="プロ・メモリアルエディタ", layout="wide")

# --- 2. 便利関数 ---
def get_image_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def add_shadow(image, offset=(10, 10), shadow_color=(0, 0, 0, 80)):
    total_w, total_h = image.width + 30, image.height + 30
    back = Image.new("RGBA", (int(total_w), int(total_h)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", image.size, shadow_color)
    back.paste(shadow, (15 + offset[0], 15 + offset[1]))
    back = back.filter(ImageFilter.GaussianBlur(10))
    back.paste(image, (15, 15), image)
    return back

# --- 3. サイドバー設定 ---
with st.sidebar:
    st.header("📋 基本設定")
    selected_size = st.selectbox("出力サイズ", list(PAPER_SIZES.keys()), index=0)
    W, H = PAPER_SIZES[selected_size]
    
    selected_frame_key = st.radio("装飾枠の選択", list(FRAME_FILES.keys()))
    frame_path = FRAME_FILES[selected_frame_key]
    
    st.write("🎨 背景色")
    bg_preset = st.selectbox("背景色プリセット", list(PRESET_BG_COLORS.keys()))
    bg_color = st.color_picker("背景カスタム", "#FFFFFF") if bg_preset == "カスタム設定 🎨" else PRESET_BG_COLORS[bg_preset]
    
    st.divider()
    st.header("📸 写真の設定")
    uploaded_file = st.file_uploader("写真をアップロード", type=["jpg", "png", "jpeg"])
    use_shadow = st.toggle("💡 写真に影をつける", value=True)
    auto_enhance = st.toggle("✨ オート補正", value=True)
    
    st.divider()
    st.header("✍️ 文字の設定")
    user_text = st.text_area("本文", value="", placeholder="メッセージを入力...", max_chars=100)
    selected_font_name = st.selectbox("フォントの種類", list(FONTS.keys()))
    text_size_init = st.slider("文字のサイズ", 10, 150, 45)
    
    st.write("🎨 文字色")
    text_preset = st.selectbox("文字色プリセット", list(PRESET_TEXT_COLORS.keys()))
    text_color = st.color_picker("文字カスタム", "#333333") if text_preset == "カスタム設定 🎨" else PRESET_TEXT_COLORS[text_preset]
    
    st.divider()
    reset_layout = st.button("🔄 配置をリセット")

# --- 4. 画像・文字作成ロジック ---
def prepare_image(file, target_w, target_h, is_auto, has_frame, shadow):
    img = Image.open(file).convert("RGBA")
    margin = 0.75 if has_frame else 0.9
    img = ImageOps.contain(img, (int(target_w * margin), int(target_h * (margin - 0.1))))
    if is_auto:
        img = ImageEnhance.Brightness(img).enhance(1.05)
        img = ImageEnhance.Contrast(img).enhance(1.1)
    if shadow: img = add_shadow(img)
    return img

def prepare_text_image(text, size, color, target_w, f_path):
    # 実行ファイルと同じ階層からフォントを探す
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

# --- 5. 状態管理 ---
# 💡 背景色（bg_color）が変わった時も、画面を強制的に書き換えるようにします
# 💡 ここに 「bg_color」が入っているかチェックしてください！
canvas_key = f"v17_{uploaded_file.name if uploaded_file else 'n'}_{selected_size}_{selected_frame_key}_{selected_font_name}_{use_shadow}_{bg_color}"

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

# --- 6. メイン画面描画 ---
st.title("📱 メモリアルフォト＆メッセージ")

# 台紙作成
base_paper = Image.new("RGBA", (int(W), int(H)), bg_color)

# 💡 枠の合成（パス指定を強化）
if frame_path:
    current_dir = os.path.dirname(__file__)
    full_frame_path = os.path.join(current_dir, frame_path)
    if os.path.exists(full_frame_path):
        waku = Image.open(full_frame_path).convert("RGBA").resize((int(W), int(H)))
        base_paper = Image.alpha_composite(base_paper, waku)
    else:
        st.error(f"⚠️ 枠 '{frame_path}' が見当たりません。GitHub上にファイルがあるか確認してください。")
        st.write("現在のフォルダ内:", os.listdir(current_dir))

canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 0)", background_image=base_paper,
    initial_drawing={"objects": objects_list} if objects_list else None,
    height=int(H), width=int(W), drawing_mode="transform", display_toolbar=False, key=canvas_key, 
)

# --- 7. 保存 ---
st.divider()
if st.button("✨ デザインを確定する", use_container_width=True, type="primary"):
    if canvas_result.image_data is not None:
        final_layer = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
        complete_page = Image.alpha_composite(base_paper, final_layer)
        st.success("✅ 準備完了！保存形式を選んでください。")
        c1, c2 = st.columns(2)
        buf_j = io.BytesIO()
        complete_page.convert("RGB").save(buf_j, format="JPEG", quality=95)
        c1.download_button("📥 通常保存 (JPEG)", buf_j.getvalue(), f"memorial_{selected_size}.jpg", "image/jpeg", use_container_width=True)
        buf_p = io.BytesIO()
        complete_page.convert("RGB").save(buf_p, format="PDF", resolution=100.0)
        c2.download_button("📥 高画質保存 (PDF)", buf_p.getvalue(), f"memorial_{selected_size}.pdf", "application/pdf", use_container_width=True)