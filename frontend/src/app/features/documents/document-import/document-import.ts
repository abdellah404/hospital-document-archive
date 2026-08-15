import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DocumentService } from '../../../core/services/document';

@Component({
  selector: 'app-document-import',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './document-import.html',
})
export class DocumentImportComponent {
  private documentService = inject(DocumentService);

  hospitalizationId = '';
  selectedFile: File | null = null;

  message = '';
  errorMessage = '';

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;

    this.selectedFile = input.files?.[0] ?? null;
  }

  upload(): void {
    if (!this.hospitalizationId || !this.selectedFile) {
      this.errorMessage =
        'Select a hospitalization and a PDF file.';

      return;
    }

    this.message = '';
    this.errorMessage = '';

    this.documentService
      .upload(
        this.hospitalizationId,
        this.selectedFile,
      )
      .subscribe({
        next: () => {
          this.message =
            'Document imported successfully.';

          this.selectedFile = null;
        },

        error: (error) => {
          this.errorMessage =
            error.error?.detail ??
            'Document import failed.';
        },
      });
  }
}