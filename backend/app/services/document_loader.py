'''
@create_time: 2026/02/09
@Author: GeChao
@File: document_loader.py
'''
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, UnstructuredExcelLoader
from langchain_core.documents import Document

from app.utils.log import get_logger

logger = get_logger(__name__)


class DocumentLoader:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self._ocr = None
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
            separators=["\n\n", "\n", "。", "！", "？", "，", "、", " ", ""],
        )

    @staticmethod
    def _build_chunk_id(filename: str, page_number: int, index: int) -> str:
        return f"{filename}::p{page_number}::{index}"

    @staticmethod
    def _build_parent_chunk_id(filename: str, page_number: int) -> str:
        return f"{filename}::p{page_number}::parent"

    def _ocr_pdf(self, file_path: str) -> list[Document]:
        """扫描版 PDF 兜底：渲染页面成图后 OCR，结果包装回 Document 列表"""
        import tempfile

        import pymupdf
        from rapidocr_onnxruntime import RapidOCR

        if self._ocr is None:
            self._ocr = RapidOCR()

        documents = []
        with pymupdf.open(file_path) as pdf:
            for page_number, page in enumerate(pdf):
                pix = page.get_pixmap(dpi=200)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    pix.save(tmp.name)
                    result, _ = self._ocr(tmp.name)
                text = "\n".join(line[1] for line in (result or []) if line and len(line) >= 2)
                documents.append(Document(page_content=text, metadata={"page": page_number}))
        return documents

    def load_document(self, file_path: str, filename: str) -> list[dict]:
        file_lower = filename.lower()

        # 不同文件类型解析成文本
        if file_lower.endswith(".pdf"):
            doc_type = "PDF"
            loader = PyPDFLoader(file_path)
        elif file_lower.endswith((".docx", ".doc")):
            doc_type = "Word"
            loader = Docx2txtLoader(file_path)
        elif file_lower.endswith((".xlsx", ".xls")):
            doc_type = "Excel"
            loader = UnstructuredExcelLoader(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {filename}")

        try:
            raw_docs = loader.load()
            # 全部页都提不出文字说明是扫描件，转 OCR 识别
            if doc_type == "PDF" and all(not (doc.page_content or "").strip() for doc in raw_docs):
                logger.info("PDF无文字层，走OCR识别: %s", filename)
                raw_docs = self._ocr_pdf(file_path)
            documents = []

            # 提取每个原始单元的正文文本
            for idx, doc in enumerate(raw_docs):
                page_text = (doc.page_content or "").strip()
                if not page_text:
                    continue
                # 文档村
                page_number = doc.metadata.get("page", idx)
                try:
                    page_number = int(page_number)
                except (TypeError, ValueError):
                    page_number = idx

                # 当页生成父块ID
                parent_chunk_id = self._build_parent_chunk_id(filename, page_number)
                texts = self._splitter.split_text(page_text)
                # 遍历切出来的小块
                for chunk_idx, text in enumerate(texts):
                    if not text.strip():
                        continue
                    documents.append({
                        "text": text.strip(),
                        "filename": filename,
                        "file_path": file_path,
                        "file_type": doc_type,
                        "page_number": page_number,
                        "chunk_id": self._build_chunk_id(filename, page_number, chunk_idx),
                        "parent_chunk_id": parent_chunk_id,
                        "root_chunk_id": parent_chunk_id,
                        "chunk_idx": chunk_idx,
                        "parent_text": page_text,
                        "chunk_level": 3,
                    })
            return documents
        except Exception as e:
            logger.exception("Document load failed file=%s", filename)
            raise Exception(f"处理文档失败: {str(e)}")


document_loader = DocumentLoader()
