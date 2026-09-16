from PIL import Image, ImageDraw

from pdf4sci.classifier import classify_image


def test_tiny_image_is_icon():
    img = Image.new("RGB", (32, 32), (10, 20, 30))
    result = classify_image(img, 32, 32)
    assert result.category == "icon"
    assert result.prefer_jpeg is False


def test_noisy_continuous_tone_image_is_photo():
    import random

    random.seed(0)
    img = Image.new("RGB", (200, 200))
    pixels = [
        (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        for _ in range(200 * 200)
    ]
    img.putdata(pixels)
    result = classify_image(img, 200, 200)
    assert result.category == "photo"
    assert result.prefer_jpeg is True


def test_flat_line_drawing_is_plot():
    img = Image.new("RGB", (400, 300), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.line((10, 10, 390, 290), fill=(0, 0, 0), width=2)
    draw.line((10, 290, 390, 10), fill=(0, 0, 0), width=2)
    result = classify_image(img, 400, 300)
    assert result.category == "plot"
    assert result.prefer_jpeg is False
