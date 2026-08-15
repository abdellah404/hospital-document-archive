import uuid
from pathlib import Path
from fastapi.responses import FileResponse
from sqlalchemy import select

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.hospitalization import Hospitalization
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.schemas import document


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


STORAGE_DIR = Path("storage/documents")
STORAGE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    hospitalization_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    hospitalization = db.get(
        Hospitalization,
        hospitalization_id,
    )

    if not hospitalization:
        raise HTTPException(
            status_code=404,
            detail="Hospitalization not found",
        )
    
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )


    document_id = uuid.uuid4()

    stored_filename = f"{document_id}.pdf"

    file_path = STORAGE_DIR / stored_filename

    try:
        with file_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)

    except Exception:
        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Failed to store document",
        )

    document = Document(
        id=document_id,
        hospitalization_id=hospitalization_id,
        original_filename=file.filename or "document.pdf",
        stored_filename=stored_filename,
        storage_path=str(file_path),
        status="IMPORTED",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document



@router.get(
    "",
    response_model=list[DocumentResponse],
)
def get_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Document)
        .order_by(Document.created_at.desc())
    ).all()

@router.get(
    "/{document_id}/file",
)
def get_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = Path(document.storage_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=document.original_filename,
    )