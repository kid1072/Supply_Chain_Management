from sqlalchemy.exc import IntegrityError

from app.core.exceptions import BusinessException


def _integrity_error_text(exc: IntegrityError) -> str:
    parts = []
    if getattr(exc, "orig", None):
        parts.append(str(exc.orig))
    parts.append(str(exc))
    return " | ".join(part for part in parts if part).lower()


def map_integrity_error_message(exc: IntegrityError) -> str:
    message = _integrity_error_text(exc)
    if any(token in message for token in ("duplicate entry", "unique constraint failed", "is not unique", "1062")):
        return "数据保存失败，存在重复数据"
    if any(token in message for token in ("foreign key constraint fails", "foreign key constraint failed", "1451", "1452")):
        return "数据保存失败，关联数据不存在或仍被其他记录引用"
    if any(token in message for token in ("not null constraint failed", "cannot be null", "1048")):
        return "数据保存失败，存在必填字段为空"
    return "数据保存失败，请检查输入后重试"


def raise_product_integrity_error(exc: IntegrityError) -> None:
    message = _integrity_error_text(exc)
    if "product_code" in message:
        raise BusinessException("商品编码已存在，请勿重复填写")
    if "barcode" in message:
        raise BusinessException("商品条码已存在，请勿重复填写")
    raise BusinessException("商品保存失败，请检查商品编码或条码是否重复")
