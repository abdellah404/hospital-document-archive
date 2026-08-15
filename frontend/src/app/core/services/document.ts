import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface DocumentResponse {
  id: string;
  hospitalization_id: string;
  original_filename: string;
  status: string;
  created_at: string;
}

@Injectable({
  providedIn: 'root',
})
export class DocumentService {
  private http = inject(HttpClient);

  private apiUrl = 'http://localhost:8000';

  upload(
    hospitalizationId: string,
    file: File,
  ): Observable<DocumentResponse> {
    const formData = new FormData();

    formData.append(
      'file',
      file,
      file.name,
    );

    return this.http.post<DocumentResponse>(
      `${this.apiUrl}/documents/upload?hospitalization_id=${hospitalizationId}`,
      formData,
    );
  }

  getDocuments(): Observable<DocumentResponse[]> {
    return this.http.get<DocumentResponse[]>(
      `${this.apiUrl}/documents`,
    );
  }
}