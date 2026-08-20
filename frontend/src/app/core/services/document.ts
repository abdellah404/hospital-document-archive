import {
  Injectable,
  inject,
} from '@angular/core';

import {
  HttpClient,
} from '@angular/common/http';

import {
  Observable,
} from 'rxjs';

import {
  environment,
} from '../../../environments/environment';


export interface DocumentResponse {
  id: string;
  hospitalization_id: string | null;
  original_filename: string;
  status: string;
  created_at: string;
}

export interface ArchivedDocument {
  id: string;
  original_filename: string;
  status: string;
  created_at: string;
  archived_at: string | null;
  patient: { id: string; cni: string; first_name: string; last_name: string };
  hospitalization: { id: string; number: string; admission_date: string | null; discharge_date: string | null };
  service: { id: string; name: string; is_active: boolean };
}

export interface ArchivedDocumentResponse {
  items: ArchivedDocument[];
  pagination: { page: number; page_size: number; total: number; total_pages: number };
}


export interface DocumentStatusResponse {
  document_id: string;
  status: string;
}


export interface AIResult {

  cni: string | null;

  first_name: string | null;

  last_name: string | null;

  hospitalization_number:
    string | null;

  service_name:
    string | null;

  admission_date:
    string | null;

  discharge_date:
    string | null;
}


export interface IdentificationResult {

  patient: {
    status: string;
    id: string | null;
  };

  hospitalization: {
    status: string;
    id: string | null;
  };

  service: {
    status: string;
    id: string | null;
  };
}


export interface DocumentReview {

  document: {
    id: string;
    filename: string;
    status: string;
  };

  ai: AIResult;

  identification:
    IdentificationResult;
}


export interface ServiceResponse {

  id: string;

  name: string;

  is_active: boolean;
}


export interface VerifyDocumentRequest {

  cni: string;

  first_name: string;

  last_name: string;

  hospitalization_number:
    string;

  service_id: string;

  admission_date: string;

  discharge_date:
    string | null;
}


export interface ArchiveResponse {

  message: string;

  document_id: string;

  patient_id: string;

  hospitalization_id: string;

  service_id: string;

  status: string;
}

export interface UpdateArchivedDocumentRequest {
  cni: string;
  first_name: string;
  last_name: string;
  hospitalization_number: string;
  service_id: string;
  admission_date: string;
  discharge_date: string | null;
}

export interface UpdateArchivedDocumentResponse extends ArchiveResponse {
  data: UpdateArchivedDocumentRequest;
}

export interface ResumeDocumentResponse {
  message: string;
  document_id: string;
  previous_status: string;
  task_id: string;
}


@Injectable({
  providedIn: 'root',
})
export class DocumentService {

  private http = inject(
    HttpClient
  );

  private apiUrl =
    environment.apiUrl;


  upload(
    file: File,
  ): Observable<DocumentResponse> {

    const formData =
      new FormData();

    formData.append(
      'file',
      file,
      file.name,
    );

    return this.http.post<DocumentResponse>(
      `${this.apiUrl}/documents/upload`,
      formData,
    );
  }

  getDocuments(): Observable<DocumentResponse[]> {
    return this.http.get<DocumentResponse[]>(`${this.apiUrl}/documents`);
  }

  searchArchived(params: Record<string, string | number>): Observable<ArchivedDocumentResponse> {
    return this.http.get<ArchivedDocumentResponse>(`${this.apiUrl}/documents/archived`, { params });
  }


  getStatus(
    documentId: string,
  ): Observable<DocumentStatusResponse> {

    return this.http.get<DocumentStatusResponse>(
      `${this.apiUrl}/documents/${documentId}/status`,
    );
  }


  getFile(
    documentId: string,
  ): Observable<Blob> {

    return this.http.get(
      `${this.apiUrl}/documents/${documentId}/file`,
      {
        responseType: 'blob',
      },
    );
  }


  getReview(
    documentId: string,
  ): Observable<DocumentReview> {

    return this.http.get<DocumentReview>(
      `${this.apiUrl}/documents/${documentId}/review`,
    );
  }


  getServices():
    Observable<ServiceResponse[]> {

    return this.http.get<ServiceResponse[]>(
      `${this.apiUrl}/services`,
    );
  }


  verify(
    documentId: string,
    data: VerifyDocumentRequest,
  ): Observable<ArchiveResponse> {

    return this.http.post<ArchiveResponse>(
      `${this.apiUrl}/documents/${documentId}/verify`,
      data,
    );
  }

  updateArchivedDocument(
    documentId: string,
    data: UpdateArchivedDocumentRequest,
  ): Observable<UpdateArchivedDocumentResponse> {
    return this.http.patch<UpdateArchivedDocumentResponse>(
      `${this.apiUrl}/documents/${documentId}/archive`,
      data,
    );
  }

  resumeProcessing(documentId: string): Observable<ResumeDocumentResponse> {
    return this.http.post<ResumeDocumentResponse>(
      `${this.apiUrl}/documents/${documentId}/resume`,
      null,
    );
  }
}
