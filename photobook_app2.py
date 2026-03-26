import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image, ImageDraw, ImageFont, ImageOps
import base64
import os
import io
import numpy as np

# --- Streamlit用パッチ (背景表示エラー回避) ---
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
# 定数・設定
# ==========================================
CARD_W = 560
PADDING = 80
CANVAS_W = CARD_W + PADDING * 2
PHOTO_MAX_PX = 350
CARD_INNER_PAD = 36 # デザイン枠の太さ目安
GAP = 12

# 背景デザインの読み込み
CARDS_DIR = "cards"
if not os.path.exists(CARDS_DIR):
    os.makedirs(CARDS_DIR)

def load_designs():
    exts = (".jpg", ".jpeg", ".png")
    files = sorted([f for f in os.listdir(CARDS_DIR) if f.lower().endswith(exts)])
    if not files: return {"（デフォルト）": None}
    return {os.path.splitext(f)[0]: os.path.join(CARDS_DIR, f) for f in files}

DESIGNS = load_designs()

# 💡 フォント指定（GitHubに上げたファイル名に合わせてください）
FONT_FILE = "msgothic.ttc" 

# ==========================================
# ユーティリティ
# ==========================================
def resize_pil(img, max_px):
    w, h = img.size
    if max(w, h) <= max_px: return img
    r = max_px / max(w, h)
    return img.resize((int(w*r), int(h*r)), Image.LANCZOS)

def pil_to_b64(img):
    buf = io.BytesIO()
    # 透過PNGとして保存してBase64化
    img.convert("RGBA").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def prepare_text_image_fitting(text, size, color, target_w, target_h, f_path):
    """
    💡 文字がターゲットの矩形に収まるまで、フォントサイズを自動的に縮小調整する
    """
    f_path_full = os.path.join(os.getcwd(), f_path)
    # Binary Searchで最適なフォントサイズを見つける
    low = 10
    high = size
    best_size = low
    
    test_img = Image.new("RGBA", (int(target_w), 500))
    test_draw = ImageDraw.Draw(test_img)

    while low <= high:
        mid = (low + high) // 2
        try: test_font = ImageFont.truetype(f_path_full, mid)
        except: test_font = ImageFont.load_default()
        
        # 簡易的な折り返し計算
        wrapped_text = ""
        current_line = ""
        for char in list(text):
            test_line = current_line + char
            if test_draw.textbbox((0, 0), test_line, font=test_font)[2] > target_w * 0.95:
                wrapped_text += current_line + "\n"
                current_line = char
            else:
                current_line = test_line
        wrapped_text += current_line
        
        # 収まるか確認
        bbox = test_draw.multiline_textbbox((0, 0), wrapped_text, font=test_font, align="center")
        tw, th = int(bbox[2] - bbox[0] + 60), int(bbox[3] - bbox[1] + 60)
        
        if tw <= target_w and th <= target_h:
            best_size = mid
            low = mid + 1
        else:
            high = mid - 1
            
    # 最適なサイズでレンダリング
    try: final_font = ImageFont.truetype(f_path_full, best_size)
    except: final_font = ImageFont.load_default()
    
    # 再度折り返し計算
    test_img = Image.new("RGBA", (int(target_w), 500))
    test_draw = ImageDraw.Draw(test_img)
    wrapped_text = ""
    current_line = ""
    for char in list(text):
        test_line = current_line + char
        if test_draw.textbbox((0, 0), test_line, font=final_font)[2] > target_w * 0.95:
            wrapped_text += current_line + "\n"
            current_line = char
        else:
            current_line = test_line
    wrapped_text += current_line

    bbox = test_draw.multiline_textbbox((0, 0), wrapped_text, font=final_font, align="center")
    tw, th = int(bbox[2] - bbox[0] + 60), int(bbox[3] - bbox[1] + 60)
    
    txt_img = Image.new("RGBA", (max(tw, 100), max(th, 50)), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.multiline_text((tw//2, th//2), wrapped_text, font=final_font, fill=color, anchor="mm", align="center")
    return txt_img, best_size

def make_bg(design_name):
    path = DESIGNS.get(design_name)
    if path and os.path.exists(path):
        bg = Image.open(path).convert("RGBA")
    else:
        bg = Image.new("RGBA", (CARD_W, 400), (245, 245, 240, 255))
    
    card_h = int(CARD_W * bg.height / bg.width)
    canvas_h = card_h + PADDING * 2
    canvas = Image.new("RGBA", (CANVAS_W, canvas_h), (210, 205, 200, 255))
    # 背景の土台
    canvas.paste(bg.resize((CARD_W, card_h)), (PADDING, PADDING))
    return canvas, card_h, canvas_h

# ==========================================
# 🤖 自動レイアウトロジック
# ==========================================
def auto_layout(photo_infos, text_defs, card_w, card_h):
    n = len(photo_infos)
    objects = []
    margin = CARD_INNER_PAD + 15
    x0, y0 = PADDING + margin, PADDING + margin
    aw, ah = card_w - margin * 2, card_h - margin * 2

    # テキストエリアを下部に確保
    all_text = "\n".join([t.get("text", "") for t in text_defs])
    if all_text:
        # 文字数が多い場合はテキストエリアを ah の最大50%まで確保
        text_zone_h = max(int(ah * 0.3), int(ah * min(0.5, len(all_text) / 200)))
        ph_area_h = ah - text_zone_h - GAP
        ph_area_h = max(ph_area_h, 40) # 最小限の写真エリア
    else:
        text_zone_h = 0
        ph_area_h = ah

    # 写真枠の分割
    def split(cols, rows, area_w, area_h, base_x, base_y):
        pw = (area_w - GAP * (cols - 1)) // cols
        ph = (area_h - GAP * (rows - 1)) // rows
        rects = []
        for r in range(rows):
            for c in range(cols):
                rects.append((base_x + c*(pw+GAP), base_y + r*(ph+GAP), pw, ph))
        return rects

    rects = []
    if n == 1: rects = [(x0, y0, aw, ph_area_h)]
    elif n == 2: rects = split(2, 1, aw, ph_area_h, x0, y0)
    elif n == 3:
        # 左に大きく1枚、右に縦2枚
        pw_l = int(aw * 0.55) - GAP // 2
        pw_r = aw - pw_l - GAP
        ph_r = (ph_area_h - GAP) // 2
        rects = [
            (x0, y0, pw_l, ph_area_h),
            (x0 + pw_l + GAP, y0, pw_r, ph_r),
            (x0 + pw_l + GAP, y0 + ph_r + GAP, pw_r, ph_r)
        ]
    elif n == 4: rects = split(2, 2, aw, ph_area_h, x0, y0)
    else:
        # それ以上はグリッド配置
        cols = 3
        rows = (n + cols - 1) // cols
        rects = split(cols, rows, aw, ph_area_h, x0, y0)

    # 写真オブジェクト追加
    for info, (rx, ry, rw, rh) in zip(photo_infos, rects):
        scale = min(rw / info["w"], rh / info["h"])
        objects.append({
            "type": "image", "src": info["src"],
            "left": int(rx + (rw - info["w"]*scale)//2),
            "top": int(ry + (rh - info["h"]*scale)//2),
            "scaleX": scale, "scaleY": scale, "originX": "left", "originY": "top"
        })
    
    # 💡 文字オブジェクト生成：Safe Area内に収める
    if all_text:
        ty = y0 + ph_area_h + GAP
        color = text_defs[0].get("fill", "#333333") if text_defs else "#333333" 
        # Safe Areaの矩形に合わせて画像を生成
        txt_img, fitted_size = prepare_text_image_fitting(
            all_text, 36, color, aw, text_zone_h, FONT_FILE
        )
        objects.append({
            "type": "image", "src": pil_to_b64(txt_img),
            # テキストエリアの中央下部に配置
            "left": x0 + (aw - txt_img.width)//2,
            "top": ty + (text_zone_h - txt_img.height)//2,
            "originX": "left", "originY": "top"
        })
        st.info(f"🤖 自動レイアウト：文字全体がSafe Areaに収まるように、フォントサイズを {fitted_size}px に縮小調整しました。")
        
    return objects

# ==========================================
# メイン UI
# ==========================================
st.set_page_config(page_title="プロ・メモリアルカード", layout="wide")
st.title("🕯️ プロ・メモリアルカード (AI自動レイアウト版)")

# セッション初期化
if "canvas_objects" not in st.session_state:
    st.session_state.canvas_objects = []
    st.session_state.processed = {} # ファイル名: info
    st.session_state.canvas_key = 0
    st.session_state.mode = "手動"
    st.session_state.design = list(DESIGNS.keys())[0]
    st.session_state.text_defs = [] # 自動モード用テキスト素材リスト

with st.sidebar:
    st.header("🛠️ 素材設定")

    # 背景デザイン
    st.subheader("🖼️ 背景デザイン")
    design_names = list(DESIGNS.keys())
    st.session_state.design = st.selectbox("デザイン切替", design_names, index=design_names.index(st.session_state.design))

    st.divider()

    # 写真追加
    st.subheader("📷 写真を追加")
    uploaded_files = st.file_uploader("写真を選択 (複数可)", accept_multiple_files=True)
    if uploaded_files:
        new_files = [f for f in uploaded_files if f.name not in st.session_state.processed]
        if new_files and st.button(f"🖼️ {len(new_files)}枚を反映"):
            for f in new_files:
                pil = Image.open(f).convert("RGBA")
                c = resize_pil(pil, PHOTO_MAX_PX)
                info = {"src": pil_to_b64(c), "w": c.width, "h": c.height}
                st.session_state.processed[f.name] = info
                # 手動モードならキャンバスに追加
                if st.session_state.mode == "手動":
                    st.session_state.canvas_objects.append({
                        "type": "image", "src": info["src"],
                        "left": PADDING + 60, "top": PADDING + 60,
                        "scaleX": 1.0, "scaleY": 1.0
                    })
            if st.session_state.mode == "AIで自動レイアウト":
                st.info("🤖 「AIで自動レイアウト」を適用を押してください")
            st.session_state.canvas_key += 1
            st.rerun()

    st.divider()

    # 文字追加
    st.subheader("✍️ 文字を追加")
    # 長文対応のためtext_areaに変更
    msg = st.text_area("文字入力", "想い出をありがとう。")
    col1, col2 = st.columns([2, 1])
    with col1: t_color = st.color_picker("文字色", "#333333")
    with col2: font_size = st.number_input("サイズ", 12, 100, 28)

    if st.button("📝 文字を追加"):
        if msg:
            text_obj = {
                "type": "i-text", "text": msg, "fill": t_color,
                "fontFamily": "ゴシック体", "fontSize": font_size,
                "left": PADDING + 80, "top": CANVAS_W//2
            }
            if st.session_state.mode == "AIで自動レイアウト":
                st.session_state.text_defs.append(text_obj)
                st.info("🤖 「AIで自動レイアウト」を適用を押してください")
            else:
                st.session_state.canvas_objects.append(text_obj)
            st.session_state.canvas_key += 1
            st.rerun()

    if st.session_state.text_defs and st.session_state.mode == "AIで自動レイアウト":
        st.caption(f"✍️ 自動モード用素材: {len(st.session_state.text_defs)}件")

    st.divider()

    # 自動レイアウト
    st.subheader("🤖 レイアウトモード")
    st.session_state.mode = st.radio("配置モード", ["手動", "AIで自動レイアウト"])
    
    if st.session_state.mode == "AIで自動レイアウト":
        if st.button("🤖 自動レイアウトを適用", type="primary", use_container_width=True):
            p_infos = list(st.session_state.processed.values())
            t_defs = st.session_state.text_defs
            if not p_infos and not t_defs:
                st.warning("写真または文字を追加してください。")
            else:
                # 一時的な背景取得でahを計算
                _, card_h_tmp, _ = make_bg(st.session_state.design)
                new_objects = auto_layout(p_infos, t_defs, CARD_W, card_h_tmp)
                st.session_state.canvas_objects = new_objects
                st.session_state.canvas_key += 1
                st.rerun()

    st.divider()
    # リセット
    if st.button("🔄 全部リセット", type="secondary"):
        for k in ["canvas_objects", "processed", "text_defs"]:
            st.session_state[k] = [] if k != "processed" else {}
        st.session_state.canvas_key += 1
        st.rerun()

# --- メインエリア ---
# キャンバス表示
bg_img, card_h, canvas_h = make_bg(st.session_state.design)

st.subheader("2. 写真・文字を配置してください")
st.caption("💡 ドラッグ: 移動　四隅□: 拡大縮小　上○: 回転　ダブルクリック: テキスト編集")

# 💡 デザイン変更時にキャンバスをリセットして背景を更新
c_key = f"canvas_{st.session_state.design}_{st.session_state.canvas_key}"

canvas_result = st_canvas(
    fill_color="rgba(0,0,0,0)",
    background_image=bg_img,
    initial_drawing={"objects": st.session_state.canvas_objects},
    height=canvas_h, width=CANVAS_W,
    drawing_mode="transform",
    key=c_key,
)

# 確定・保存
st.divider()
if st.button("✅ 完成画像を確定する", type="primary", use_container_width=True):
    if canvas_result.image_data is not None:
        rgba = Image.fromarray(canvas_result.image_data.astype(np.uint8), "RGBA")
        merged = Image.alpha_composite(bg_img.convert("RGBA"), rgba)
        # 透過背景を白にする
        final_merged = Image.new("RGBA", merged.size, "white")
        final_merged.paste(merged, (0,0), merged)
        # カード部分をトリミング
        final = final_merged.crop((PADDING, PADDING, PADDING + CARD_W, PADDING + card_h)).convert("RGB")
        
        st.image(final, caption="完成プレビュー", use_container_width=True)
        buf = io.BytesIO()
        final.save(buf, format="JPEG", quality=95)
        st.download_button("📥 完成品をダウンロード (JPEG)", buf.getvalue(), "memorial_card.jpg", "image/jpeg")