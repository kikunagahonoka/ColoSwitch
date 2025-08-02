import gradio as gr
from PIL import Image
import numpy as np
import io
import tempfile
import re

# 色抽出（透明ピクセルを除外）
def get_colors(image):
    image = image.convert("RGBA").resize((100, 100))
    arr = np.array(image)

    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    mask = alpha > 0
    rgb_filtered = rgb[mask]

    if len(rgb_filtered) == 0:
        return []

    unique, counts = np.unique(rgb_filtered.reshape(-1, 3), axis=0, return_counts=True)
    top_indices = counts.argsort()[-10:][::-1]
    top_colors = unique[top_indices]
    return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in top_colors]

# rgba → #rrggbb に変換
def parse_color_code(color):
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        return color

    match = re.match(r'rgba?\((\d+\.?\d*),\s*(\d+\.?\d*),\s*(\d+\.?\d*)', color)
    if match:
        r, g, b = map(lambda x: int(float(x)), match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"

    raise ValueError(f"不正なカラーコード: {color}")

# 色置換（透明ピクセルはスキップ）
def replace_color_with_tolerance(image, color_from, color_to, tolerance):
    image = image.convert("RGBA")
    arr = np.array(image)

    r1, g1, b1 = [int(color_from[i:i+2], 16) for i in (1, 3, 5)]
    r2, g2, b2 = [int(color_to[i:i+2], 16) for i in (1, 3, 5)]

    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    diff = rgb - np.array([r1, g1, b1])
    distance = np.sqrt(np.sum(diff ** 2, axis=2))

    # α > 0 のピクセルだけ対象に
    mask = (distance <= tolerance) & (alpha > 0)

    arr[mask, 0] = r2
    arr[mask, 1] = g2
    arr[mask, 2] = b2

    return Image.fromarray(arr, mode="RGBA")

# メイン処理
def process(image, selected_color, color_to, tolerance):
    try:
        color_from_hex = parse_color_code(selected_color)
        color_to_hex = parse_color_code(color_to)

        result = replace_color_with_tolerance(image, color_from_hex, color_to_hex, tolerance)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            result.save(tmp, format="PNG")
            tmp_path = tmp.name

        return result, gr.File(value=tmp_path, visible=True), gr.Textbox(value="", visible=False)

    except Exception as e:
        return None, None, gr.Textbox(value=f"⚠️ エラー: {str(e)}", visible=True)

# セレクトボックスに色一覧を入れる
def extract_and_return_choices(image):
    colors = get_colors(image)
    if not colors:
        return gr.update(choices=[], value=None), "⚠️ 有効な色が見つかりませんでした（完全に透明な画像？）"
    return gr.update(choices=colors, value=colors[0]), ", ".join(colors)

# UI構成
with gr.Blocks() as demo:
    gr.Markdown("## ColoSwitch")

    with gr.Row():
        image_input = gr.Image(type="pil", label="① 画像をアップロード")
        extract_btn = gr.Button("② 色を抽出して選択肢に反映")

    with gr.Row():
        selected_color = gr.Dropdown(label="③ 変えたい色", choices=[], interactive=True)
        color_to = gr.ColorPicker(label="④ 変更後の色", value="#000000")

    tolerance_slider = gr.Slider(minimum=0, maximum=100, value=30, step=1, label="⑤ 類似色の許容範囲")

    convert_btn = gr.Button("🚀 色を変換")
    color_output = gr.Textbox(label="抽出された代表色一覧", interactive=False)
    image_output = gr.Image(type="pil", label="変換後の画像")
    download_output = gr.File(label="PNGダウンロード", visible=False)
    error_msg = gr.Textbox(label="エラー表示", visible=False)

    extract_btn.click(fn=extract_and_return_choices, inputs=image_input, outputs=[selected_color, color_output])

    convert_btn.click(
        process,
        inputs=[image_input, selected_color, color_to, tolerance_slider],
        outputs=[image_output, download_output, error_msg]
    )

demo.launch()
