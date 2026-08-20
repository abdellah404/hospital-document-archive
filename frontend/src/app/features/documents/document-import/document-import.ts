import {
  Component,
  ChangeDetectorRef,
  inject,
  OnDestroy,
  OnInit,
} from '@angular/core';

import {
  DomSanitizer,
  SafeResourceUrl,
} from '@angular/platform-browser';

import {
  FormsModule,
} from '@angular/forms';

import {
  Router,
} from '@angular/router';

import {
  DocumentService,
  DocumentReview,
  AIResult,
} from '../../../core/services/document';


type WorkflowStep =
  | 'import'
  | 'ocr'
  | 'ai'
  | 'review'
  | 'verify'
  | 'archived';


interface ExtractedInformation {

  cni: string;

  firstName: string;

  lastName: string;

  hospitalizationNumber:
    string;

  serviceId: string;

  serviceName: string;

  admissionDate: string;

  dischargeDate: string;
}


@Component({
  selector:
    'app-document-import',

  standalone: true,

  imports: [
    FormsModule,
  ],

  templateUrl:
    './document-import.html',

  styleUrl:
    './document-import.css',
})
export class DocumentImportComponent
  implements OnDestroy, OnInit {

  private documentService =
    inject(DocumentService);

  private sanitizer =
    inject(DomSanitizer);

  private changeDetector =
    inject(ChangeDetectorRef);

  private router =
    inject(Router);


  readonly steps = [
    { key: 'import', label: 'Importer' },
    { key: 'review', label: 'Réviser' },
    { key: 'verify', label: 'Vérifier et archiver' },
  ] as const;


  currentStep:
    WorkflowStep =
    'import';


  selectedFile:
    File | null =
    null;


  documentId:
    string | null =
    null;


  isProcessing = false;

  message = '';

  errorMessage = '';

  processingMessage = '';

  processingPercent = 0;


  services: {
    id: string;
    name: string;
    is_active: boolean;
  }[] = [];


  extractedInformation:
    ExtractedInformation = {

    cni: '',

    firstName: '',

    lastName: '',

    hospitalizationNumber: '',

    serviceId: '',

    serviceName: '',

    admissionDate: '',

    dischargeDate: '',
  };


  private pdfUrl:
    string | null =
    null;


  pdfViewerUrl:
    SafeResourceUrl | null =
    null;


  private pollTimer:
    ReturnType<typeof setTimeout>
    | null =
    null;

  private reviewLoadAttempts = 0;

  private waitingForResumedWorker = false;

  private resumedStatusAttempts = 0;


  ngOnInit(): void {
    const state = (history.state ?? {}) as {
      documentId?: string;
      resumed?: boolean;
    };

    if (!state.documentId) {
      return;
    }

    this.documentId = state.documentId;
    this.waitingForResumedWorker = state.resumed === true;
    this.isProcessing = true;
    this.currentStep = 'ocr';
    this.processingPercent = 10;
    this.processingMessage = this.waitingForResumedWorker
      ? 'Traitement relancé. Reprise du document…'
      : 'Chargement du document…';
    this.loadPdf();
    this.loadServices();
    this.pollDocumentStatus();
  }


  // ========================================================
  // FILE
  // ========================================================

  onFileSelected(
    event: Event,
  ): void {

    const input =
      event.target as
      HTMLInputElement;

    const file =
      input.files?.[0] ??
      null;

    this.message = '';

    this.errorMessage = '';

    if (!file) {

      this.selectedFile =
        null;

      return;
    }

    if (
      file.type !==
      'application/pdf'
    ) {

      this.selectedFile =
        null;

      this.errorMessage =
        'Seuls les fichiers PDF sont acceptés.';

      return;
    }

    this.selectedFile =
      file;

    this.currentStep =
      'import';
  }


  // ========================================================
  // IMPORT
  // ========================================================

  importPdf(): void {

    if (!this.selectedFile) {

      this.errorMessage =
        'Veuillez sélectionner un document PDF.';

      return;
    }

    this.isProcessing =
      true;

    this.errorMessage =
      '';

    this.message =
      '';

    this.processingMessage =
      'Téléversement du PDF…';


    this.documentService
      .upload(this.selectedFile)
      .subscribe({

        next: (document) => {

          this.documentId =
            document.id;

          this.currentStep =
            'ocr';

          this.isProcessing =
            true;

          this.message =
            'PDF importé avec succès.';

          this.processingMessage =
            'Document reçu. Le traitement en arrière-plan a démarré.';

          this.processingPercent = 5;

          this.reviewLoadAttempts = 0;

          this.loadPdf();

          this.loadServices();

          this.pollDocumentStatus();

          this.changeDetector.detectChanges();
        },

        error: (error) => {

          this.isProcessing =
            false;

          this.processingMessage =
            '';

          this.errorMessage =
            error.error?.detail ??
            'Échec de l’importation du PDF.';
        },
      });
  }


  // ========================================================
  // BACKGROUND STATUS
  // ========================================================

  private pollDocumentStatus(): void {

    if (!this.documentId) {
      return;
    }

    this.documentService
      .getStatus(this.documentId)
      .subscribe({

        next: (result) => {

          const documentStatus =
            result.status.trim().toUpperCase();

          switch (
            documentStatus
          ) {

            case 'IMPORTED':
              this.currentStep = 'ocr';
              this.processingPercent = 10;

              this.isProcessing =
                true;

              this.processingMessage =
                'En attente du traitement du document…';

              this.scheduleStatusPoll();

              break;


            case 'OCR_PROCESSING':
              this.waitingForResumedWorker = false;
              this.currentStep = 'ocr';
              this.processingPercent = 40;

              this.isProcessing =
                true;

              this.processingMessage =
                'Le document est en cours d’analyse…';

              this.scheduleStatusPoll();

              break;


            case 'AI_PROCESSING':
              this.waitingForResumedWorker = false;
              this.currentStep = 'ai';
              this.processingPercent = 75;

              this.isProcessing =
                true;

              this.processingMessage =
                'Extraction des informations du patient en cours…';

              this.scheduleStatusPoll();

              break;


            case 'READY_FOR_REVIEW':
              this.waitingForResumedWorker = false;
              this.stopPolling();
              this.processingPercent = 100;
              this.currentStep = 'review';
              this.isProcessing = false;
              this.processingMessage = '';
              this.loadReview();

              break;


            case 'ARCHIVED':

              this.stopPolling();

              this.currentStep =
                'archived';

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 100;

              break;


            case 'OCR_ERROR':

              if (this.waitForResumedWorker()) break;

              this.stopPolling();

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 0;

              this.errorMessage =
                'Échec du traitement du document.';

              break;


            case 'AI_ERROR':

              if (this.waitForResumedWorker()) break;

              this.stopPolling();

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 0;

              this.errorMessage =
                'Échec de l’extraction des informations.';

              break;


            case 'PROCESSING_ERROR':

              if (this.waitForResumedWorker()) break;

              this.stopPolling();

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 0;

              this.errorMessage =
                'Le traitement du document a échoué.';

              break;


            case 'ARCHIVE_ERROR':

              if (this.waitForResumedWorker()) break;

              this.stopPolling();

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 0;

              this.errorMessage =
                'Le traitement en arrière-plan n’a pas pu aboutir.';

              break;


            default:

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.errorMessage =
                `Statut de document inconnu : ${documentStatus}`;
          }

          this.changeDetector.detectChanges();
        },

        error: (error) => {

          this.isProcessing =
            false;

          this.processingMessage =
            '';

          this.errorMessage =
            error.error?.detail ??
            'Impossible de vérifier le statut du document.';

          this.changeDetector.detectChanges();
        },
      });
  }


  private scheduleStatusPoll(): void {

    if (this.pollTimer) {

      clearTimeout(
        this.pollTimer
      );
    }

    this.pollTimer =
      setTimeout(
        () => {

          this.pollDocumentStatus();

        },
        1500,
      );
  }


  private waitForResumedWorker(): boolean {
    if (!this.waitingForResumedWorker || this.resumedStatusAttempts >= 20) {
      return false;
    }

    this.resumedStatusAttempts += 1;
    this.isProcessing = true;
    this.processingMessage = 'Traitement relancé. En attente du démarrage…';
    this.scheduleStatusPoll();
    return true;
  }


  // ========================================================
  // REVIEW
  // ========================================================

  private loadReview(): void {

    if (!this.documentId) {
      return;
    }

    this.documentService
      .getReview(
        this.documentId
      )
      .subscribe({

        next: (review) => {
          // Accept both the current nested response and the older flat
          // response shape so a backend/frontend restart cannot leave the
          // import screen spinning after a successful 200 response.
          const response = review as DocumentReview & {
            ai_result?: AIResult;
            matched_service_id?: string | null;
          };

          const ai = response.ai ?? response.ai_result ?? {
            cni: null,
            first_name: null,
            last_name: null,
            hospitalization_number: null,
            service_name: null,
            admission_date: null,
            discharge_date: null,
          };

          const serviceId =
            response.identification?.service?.id
            ?? response.matched_service_id
            ?? '';

          this.extractedInformation = {

            cni:
              ai.cni ?? '',

            firstName:
              ai.first_name ?? '',

            lastName:
              ai.last_name ?? '',

            hospitalizationNumber:
              ai.hospitalization_number
              ?? '',

            serviceId,

            serviceName:
              ai.service_name ?? '',

            admissionDate:
              ai.admission_date ?? '',

            dischargeDate:
              ai.discharge_date ?? '',
          };

          this.isProcessing =
            false;

          this.processingPercent = 100;

          this.currentStep =
            'review';

          this.message =
            'Informations extraites. Vérifiez chaque champ.';

          this.reviewLoadAttempts = 0;

          this.changeDetector.detectChanges();
        },

        error: (error) => {
          // A READY status and the review endpoint can cross in flight when
          // the worker and API use different DB connections. Retry briefly
          // instead of leaving the user on a blank, apparently stuck screen.
          if (this.reviewLoadAttempts < 5) {
            this.reviewLoadAttempts += 1;
            this.processingMessage =
              'Document prêt. Chargement des informations extraites…';
            this.reviewRetryTimer();
            return;
          }

          this.isProcessing = false;
          this.processingMessage = '';
          this.errorMessage =
            error.error?.detail ??
            'Impossible de charger la révision du document.';

          this.changeDetector.detectChanges();
        },
      });
  }


  private reviewRetryTimer(): void {
    if (this.pollTimer) {
      clearTimeout(this.pollTimer);
    }

    this.pollTimer = setTimeout(() => {
      this.loadReview();
    }, 1000);
  }


  // ========================================================
  // SERVICES
  // ========================================================

  private loadServices(): void {

    this.documentService
      .getServices()
      .subscribe({

        next: (services) => {

          this.services =
            services;
        },

        error: () => {

          this.errorMessage =
            'Impossible de charger les services hospitaliers.';
        },
      });
  }


  // ========================================================
  // VERIFY SCREEN
  // ========================================================

  openVerification(): void {

    this.errorMessage =
      '';

    if (
      !this.isInformationComplete()
    ) {

      this.errorMessage =
        'Veuillez remplir tous les champs obligatoires.';

      return;
    }

    if (
      !this.areDatesValid()
    ) {

      this.errorMessage =
        'La date de sortie ne peut pas être antérieure à la date d’admission.';

      return;
    }

    this.currentStep =
      'verify';

    this.message =
      'Vérifiez les informations avec le PDF original.';
  }


  correctInformation(): void {

    this.currentStep =
      'review';

    this.message =
      'Vous pouvez corriger les informations extraites.';
  }


  // ========================================================
  // VERIFY + ARCHIVE
  // ========================================================

  verifyAndArchive(): void {

    if (!this.documentId) {
      return;
    }

    if (
      !this.isInformationComplete()
    ) {

      this.errorMessage =
      'Remplissez tous les champs obligatoires avant l’archivage.';

      return;
    }

    if (
      !this.areDatesValid()
    ) {

      this.errorMessage =
        'Discharge date cannot be before admission date.';

      return;
    }

    this.isProcessing =
      true;

    this.errorMessage =
      '';

    this.message =
      '';

    this.processingMessage =
        'Enregistrement des informations et archivage du document…';


    this.documentService
      .verify(
        this.documentId,
        {

          cni:
            this.extractedInformation.cni,

          first_name:
            this.extractedInformation.firstName,

          last_name:
            this.extractedInformation.lastName,

          hospitalization_number:
            this.extractedInformation
              .hospitalizationNumber,

          service_id:
            this.extractedInformation
              .serviceId,

          admission_date:
            this.extractedInformation
              .admissionDate,

          discharge_date:
            this.extractedInformation
              .dischargeDate ||
            null,
        },
      )
      .subscribe({

        next: (response) => {

          this.isProcessing =
            false;

          this.processingMessage =
            '';

          this.message =
            response.message;

          this.currentStep =
            'archived';

          this.changeDetector.detectChanges();

          this.router.navigate([
            '/dashboard',
          ]);
        },

        error: (error) => {

          this.isProcessing =
            false;

          this.processingMessage =
            '';

          this.errorMessage =
            error.error?.detail ??
            'Le document n’a pas pu être archivé.';

          this.changeDetector.detectChanges();
        },
      });
  }


  // ========================================================
  // PDF
  // ========================================================

  private loadPdf(): void {

    if (!this.documentId) {
      return;
    }

    this.documentService
      .getFile(this.documentId)
      .subscribe({

        next: (blob) => {

          this.revokePdfUrl();

          this.pdfUrl =
            URL.createObjectURL(
              blob
            );

          this.pdfViewerUrl =
            this.sanitizer
              .bypassSecurityTrustResourceUrl(
                this.pdfUrl
              );
        },

        error: () => {

          this.errorMessage =
            'Impossible de charger l’aperçu du PDF.';
        },
      });
  }


  private revokePdfUrl(): void {

    if (this.pdfUrl) {

      URL.revokeObjectURL(
        this.pdfUrl
      );

      this.pdfUrl =
        null;

      this.pdfViewerUrl =
        null;
    }
  }


  // ========================================================
  // VALIDATION
  // ========================================================

  private isInformationComplete():
    boolean {

    const info =
      this.extractedInformation;

    return Boolean(

      info.cni.trim()

      && info.firstName.trim()

      && info.lastName.trim()

      && info.hospitalizationNumber.trim()

      && info.serviceId.trim()

      && info.admissionDate.trim()
    );
  }


  private areDatesValid():
    boolean {

    const admission =
      this.extractedInformation
        .admissionDate;

    const discharge =
      this.extractedInformation
        .dischargeDate;

    if (
      !admission ||
      !discharge
    ) {

      return true;
    }

    return discharge >= admission;
  }


  // ========================================================
  // RESET
  // ========================================================

  resetWorkflow(): void {

    this.stopPolling();

    this.revokePdfUrl();

    this.currentStep =
      'import';

    this.selectedFile =
      null;

    this.documentId =
      null;

    this.reviewLoadAttempts = 0;

    this.isProcessing =
      false;

    this.message =
      '';

    this.errorMessage =
      '';

    this.processingMessage =
      '';

    this.processingPercent = 0;

    this.extractedInformation = {

      cni: '',

      firstName: '',

      lastName: '',

      hospitalizationNumber: '',

      serviceId: '',

      serviceName: '',

      admissionDate: '',

      dischargeDate: '',
    };
  }


  private stopPolling(): void {

    if (this.pollTimer) {

      clearTimeout(
        this.pollTimer
      );

      this.pollTimer =
        null;
    }
  }


  ngOnDestroy(): void {

    this.stopPolling();

    this.revokePdfUrl();
  }


  // ========================================================
  // PROGRESS
  // ========================================================

  isStepActive(step: 'import' | 'review' | 'verify'): boolean {
    if (step === 'import') return ['import', 'ocr', 'ai'].includes(this.currentStep);
    return this.currentStep === step;
  }

  isStepCompleted(step: 'import' | 'review' | 'verify'): boolean {
    const visibleOrder = ['import', 'review', 'verify', 'archived'];
    const currentVisibleStep = this.currentStep === 'ocr' || this.currentStep === 'ai'
      ? 'import'
      : this.currentStep;
    return visibleOrder.indexOf(step) < visibleOrder.indexOf(currentVisibleStep);
  }
}
