import { DatePipe } from '@angular/common';
import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthService } from '../../../core/services/auth';
import {
  ArchivedDocument,
  DocumentService,
  ServiceResponse,
  UpdateArchivedDocumentRequest,
} from '../../../core/services/document';

@Component({
  selector: 'app-document-details',
  standalone: true,
  imports: [DatePipe, MatIconModule, ReactiveFormsModule],
  templateUrl: './document-details.html',
  styleUrl: './document-details.css',
})
export class DocumentDetailsComponent implements OnDestroy, OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly documentService = inject(DocumentService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly fb = inject(FormBuilder);
  private objectUrl: string | null = null;

  readonly currentUser = inject(AuthService).currentUser;
  readonly document = signal<ArchivedDocument | null>(null);
  readonly services = signal<ServiceResponse[]>([]);
  readonly previewUrl = signal<SafeResourceUrl | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly editing = signal(false);
  readonly confirming = signal(false);
  readonly errorMessage = signal('');
  readonly editError = signal('');
  readonly successMessage = signal('');

  readonly editForm = this.fb.nonNullable.group({
    cni: ['', Validators.required],
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    hospitalization_number: ['', Validators.required],
    service_id: ['', Validators.required],
    admission_date: ['', Validators.required],
    discharge_date: [''],
  });

  ngOnInit(): void {
    const document = history.state?.document as ArchivedDocument | undefined;
    if (!document || document.id !== this.route.snapshot.paramMap.get('documentId')) {
      this.loading.set(false);
      this.errorMessage.set('Les informations de ce document ne sont plus disponibles. Revenez à la recherche et sélectionnez le document à nouveau.');
      return;
    }

    this.document.set(document);
    this.documentService.getFile(document.id).subscribe({
      next: (file) => {
        this.objectUrl = URL.createObjectURL(file);
        this.previewUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(this.objectUrl));
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('Impossible de charger le PDF.');
      },
    });
  }

  startEditing(): void {
    const document = this.document();
    if (!document || this.currentUser()?.role !== 'ADMIN') return;

    this.editForm.reset({
      cni: document.patient.cni,
      first_name: document.patient.first_name,
      last_name: document.patient.last_name,
      hospitalization_number: document.hospitalization.number,
      service_id: document.service.id,
      admission_date: document.hospitalization.admission_date ?? '',
      discharge_date: document.hospitalization.discharge_date ?? '',
    });
    this.editError.set('');
    this.successMessage.set('');
    this.confirming.set(false);
    this.editing.set(true);

    if (!this.services().length) {
      this.documentService.getServices().subscribe({
        next: services => this.services.set(services),
        error: error => this.editError.set(this.apiError(error)),
      });
    }
  }

  cancelEditing(): void {
    this.editing.set(false);
    this.confirming.set(false);
    this.editError.set('');
    this.editForm.reset();
  }

  requestSave(): void {
    this.editError.set('');
    const raw = this.editForm.getRawValue();
    const requiredText = [raw.cni, raw.first_name, raw.last_name, raw.hospitalization_number];
    if (this.editForm.invalid || requiredText.some(value => !value.trim())) {
      this.editForm.markAllAsTouched();
      this.editError.set('Veuillez renseigner tous les champs obligatoires.');
      return;
    }

    const { admission_date, discharge_date } = raw;
    if (discharge_date && discharge_date < admission_date) {
      this.editError.set('La date de sortie ne peut pas être antérieure à la date d’admission.');
      return;
    }
    this.confirming.set(true);
  }

  confirmSave(): void {
    const document = this.document();
    if (!document || this.saving()) return;

    const raw = this.editForm.getRawValue();
    const payload: UpdateArchivedDocumentRequest = {
      ...raw,
      cni: raw.cni.trim(),
      first_name: raw.first_name.trim(),
      last_name: raw.last_name.trim(),
      hospitalization_number: raw.hospitalization_number.trim(),
      discharge_date: raw.discharge_date || null,
    };

    this.saving.set(true);
    this.editError.set('');
    this.documentService.updateArchivedDocument(document.id, payload).subscribe({
      next: response => {
        const service = this.services().find(item => item.id === response.service_id)
          ?? (document.service.id === response.service_id ? document.service : null);
        this.document.set({
          ...document,
          status: response.status,
          patient: {
            ...document.patient,
            id: response.patient_id,
            cni: response.data.cni,
            first_name: response.data.first_name,
            last_name: response.data.last_name,
          },
          hospitalization: {
            ...document.hospitalization,
            id: response.hospitalization_id,
            number: response.data.hospitalization_number,
            admission_date: response.data.admission_date,
            discharge_date: response.data.discharge_date,
          },
          service: service ?? {
            id: response.service_id,
            name: document.service.name,
            is_active: document.service.is_active,
          },
        });
        this.saving.set(false);
        this.editing.set(false);
        this.confirming.set(false);
        this.successMessage.set('Les informations du document archivé ont été mises à jour.');
      },
      error: error => {
        this.saving.set(false);
        this.confirming.set(false);
        this.editError.set(this.apiError(error));
      },
    });
  }

  goBack(): void {
    void this.router.navigate(['/documents/search']);
  }

  ngOnDestroy(): void {
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
  }

  private apiError(error: { error?: { detail?: string | Array<{ msg?: string }> } }): string {
    const detail = error.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map(item => item.msg).filter(Boolean).join(' ') || 'Une erreur est survenue.';
    return 'Une erreur est survenue.';
  }
}
