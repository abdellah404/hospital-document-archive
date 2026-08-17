import {
  Component,
  ChangeDetectorRef,
  inject,
  OnDestroy,
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
  implements OnDestroy {

  private documentService =
    inject(DocumentService);

  private sanitizer =
    inject(DomSanitizer);

  private changeDetector =
    inject(ChangeDetectorRef);

  private router =
    inject(Router);


  readonly steps = [
    {
      key: 'import',
      label: 'Import PDF',
    },
    {
      key: 'ocr',
      label: 'OCR',
    },
    {
      key: 'ai',
      label: 'Gemini AI',
    },
    {
      key: 'review',
      label: 'Review information',
    },
    {
      key: 'verify',
      label: 'Verify & archive',
    },
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
        'Only PDF files are accepted.';

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
        'Please select a PDF document first.';

      return;
    }

    this.isProcessing =
      true;

    this.errorMessage =
      '';

    this.message =
      '';

    this.processingMessage =
      'Uploading PDF...';


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
            'PDF imported successfully.';

          this.processingMessage =
            'Document received. Background processing started.';

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
            'PDF import failed.';
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
                'Waiting for background OCR job...';

              this.scheduleStatusPoll();

              break;


            case 'OCR_PROCESSING':
              this.currentStep = 'ocr';
              this.processingPercent = 40;

              this.isProcessing =
                true;

              this.processingMessage =
                'OCR is reading the PDF...';

              this.scheduleStatusPoll();

              break;


            case 'AI_PROCESSING':
              this.currentStep = 'ai';
              this.processingPercent = 75;

              this.isProcessing =
                true;

              this.processingMessage =
                'Gemini AI is extracting the patient information...';

              this.scheduleStatusPoll();

              break;


            case 'READY_FOR_REVIEW':
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

              this.stopPolling();

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 0;

              this.errorMessage =
                'OCR processing failed.';

              break;


            case 'AI_ERROR':

              this.stopPolling();

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 0;

              this.errorMessage =
                'Gemini AI processing failed.';

              break;


            case 'PROCESSING_ERROR':

              this.stopPolling();

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 0;

              this.errorMessage =
                'Background document processing failed.';

              break;


            case 'ARCHIVE_ERROR':

              this.stopPolling();

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.processingPercent = 0;

              this.errorMessage =
                'The background job could not finish.';

              break;


            default:

              this.isProcessing =
                false;

              this.processingMessage =
                '';

              this.errorMessage =
                `Unknown document status: ${documentStatus}`;
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
            'Could not check document status.';

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
            'Information extracted. Please review every field.';

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
              'Document is ready. Loading extracted information...';
            this.reviewRetryTimer();
            return;
          }

          this.isProcessing = false;
          this.processingMessage = '';
          this.errorMessage =
            error.error?.detail ??
            'Could not load document review.';

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
            'Could not load hospital services.';
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
        'Please complete all required information.';

      return;
    }

    if (
      !this.areDatesValid()
    ) {

      this.errorMessage =
        'Discharge date cannot be before admission date.';

      return;
    }

    this.currentStep =
      'verify';

    this.message =
      'Please verify the information against the original PDF.';
  }


  correctInformation(): void {

    this.currentStep =
      'review';

    this.message =
      'You can correct the extracted information.';
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
        'Complete all required information before archiving.';

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
      'Saving verified information and archiving document...';


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
            'Document could not be archived.';

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
            'Could not load the PDF preview.';
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

  isStepCompleted(
    step: WorkflowStep,
  ): boolean {

    const order:
      WorkflowStep[] = [

      'import',

      'ocr',

      'ai',

      'review',

      'verify',

      'archived',
    ];

    return (
      order.indexOf(step)
      <
      order.indexOf(
        this.currentStep
      )
    );
  }
}
