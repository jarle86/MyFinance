"""OCR Agent (A1) - Image processing for MyFinance.

Extracts text and monetary values from receipt images.
"""

import base64
import os
from io import BytesIO
from typing import Optional

from PIL import Image
import fitz

from core.config_loader import get_task_ocr
from core.ai_utils import generate_json_response, LLMClient, get_model_for_task


class OCRAgent:
    """Agent A1: Extracts text and values from images."""

    def __init__(self):
        """Initialize the OCR agent."""
        self._llm = LLMClient()

    def _get_task_prompt(self) -> str:
        """Get the OCR prompt from config.

        Returns:
            Prompt from sistema_config

        Raises:
            ValueError: If TASK_OCR not configured in database
        """
        prompt = get_task_ocr()

        if not prompt:
            raise ValueError(
                "TASK_OCR not configured in sistema_config. "
                "Add the prompt to the database before running."
            )

        return prompt

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 for vision model."""
        with Image.open(image_path) as img:
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _encode_image_pil(self, img: Image.Image) -> str:
        """Encode PIL image to base64."""
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def process(self, image_path: str) -> dict:
        """Process an image and extract receipt data.

        Args:
            image_path: Path to the image file

        Returns:
            Dict with extracted data
        """
        if not os.path.exists(image_path):
            return {
                "response": "Imagen no encontrada",
                "error": "image_not_found",
            }

        try:
            with Image.open(image_path) as img:
                width, height = img.size
                if width < 300 or height < 300:
                    return {
                        "response": "Imagen muy pequeña. Use una imagen más clara.",
                        "error": "image_too_small",
                    }

                return self._process_with_vision(img)

        except Exception:
            return {
                "response": "No se pudo leer la imagen. Use JPEG, PNG o PDF.",
                "error": "invalid_image",
            }

    def process_pdf(self, pdf_path: str) -> dict:
        """Process first page of PDF and extract receipt data.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dict with extracted data
        """
        if not os.path.exists(pdf_path):
            return {
                "response": "PDF no encontrado",
                "error": "pdf_not_found",
            }

        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return {
                    "response": "PDF vacío",
                    "error": "empty_pdf",
                }

            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            return self._process_with_vision(img)

        except Exception as e:
            return {
                "response": f"Error al procesar PDF: {str(e)}",
                "error": "pdf_processing_error",
            }

    def _process_with_vision(self, image: Image.Image) -> dict:
        """Process image using vision model.

        Args:
            image: PIL Image object

        Returns:
            Dict with extracted data
        """
        try:
            prompt = self._get_task_prompt()
            image_b64 = self._encode_image_pil(image)

            from core.ai_utils import generate_json_response
            
            messages = [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                        {
                            "type": "text",
                            "text": "Analiza la imagen y extrae los datos contables solicitados.",
                        },
                    ],
                },
            ]

            data = generate_json_response(
                prompt="Extrae datos del recibo.",
                model=get_model_for_task("A2"),
                temperature=0.2,
                max_tokens=tokens if 'tokens' in locals() else 1024,
                system_prompt=prompt,
                messages=messages # Passes vision messages directly
            )

            return {
                "response": f"Recibo procesado: {data.get('monto', '?')} - {data.get('proveedor', '?')}",
                "data": data,
                "ocr_completed": True,
            }

        except Exception as e:
            return {
                "response": f"OCR completado: {str(e)}",
                "data": {
                    "monto": None,
                    "fecha": None,
                    "proveedor": None,
                    "categoria": None,
                },
                "ocr_required": True,
                "error": str(e),
            }
