import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router } from '@angular/router';
import { ArchivedDocument, DocumentService } from '../../../core/services/document';

@Component({
  selector: 'app-document-search',
  standalone: true,
  imports: [FormsModule, MatIconModule, MatTooltipModule, CommonModule],
  templateUrl: './document-search.html',
  styleUrl: './document-search.css',
})
export class DocumentSearchComponent implements OnInit {
  private readonly documentService = inject(DocumentService);
  private readonly router = inject(Router);
  query = '';
  dateMode: 'all' | 'date' | 'month' | 'year' | 'last_days' | 'last_months' = 'all';
  date = '';
  month = '';
  year: number | null = null;
  lastDays: number | null = null;
  lastMonths: number | null = null;
  readonly loading = signal(false);
  readonly errorMessage = signal('');
  readonly documents = signal<ArchivedDocument[]>([]);
  readonly total = signal(0);


  ngOnInit(): void {
    this.search();
  }

  search(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    const params: Record<string, string> = { page: '1', page_size: '50' };
    const value = this.query.trim();
    if (value) params['q'] = value;

    if (this.dateMode === 'date' && this.date) params['date'] = this.date;
    if (this.dateMode === 'month' && this.month) params['month'] = this.month;
    if (this.dateMode === 'year' && this.year) params['year'] = String(this.year);
    if (this.dateMode === 'last_days' && this.lastDays) params['last_days'] = String(this.lastDays);
    if (this.dateMode === 'last_months' && this.lastMonths) params['last_months'] = String(this.lastMonths);

    this.documentService.searchArchived(params).subscribe({
      next: result => { this.documents.set(result.items); this.total.set(result.pagination.total); this.loading.set(false); },
      error: error => { this.loading.set(false); this.errorMessage.set(error.error?.detail ?? 'Impossible de charger les documents archivés.'); },
    });
  }

  onDateModeChange(): void {
    this.date = '';
    this.month = '';
    this.year = null;
    this.lastDays = null;
    this.lastMonths = null;
  }

  openDetails(document: ArchivedDocument): void {
    this.router.navigate(['/documents', document.id]);
  }

  clear(): void { this.query = ''; this.search(); }
}
