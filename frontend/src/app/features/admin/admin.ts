import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { ActivatedRoute } from '@angular/router';
import { AuthService } from '../../core/services/auth';
import { AdminService, AuditLog, ServiceItem } from '../../core/services/admin';
import { User } from '../../core/models/user';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [DatePipe, FormsModule, ReactiveFormsModule, MatIconModule, MatTooltipModule],
  templateUrl: './admin.html',
  styleUrl: './admin.css',
})
export class AdminComponent implements OnInit {
  private readonly admin = inject(AdminService);
  private readonly fb = inject(FormBuilder);
  private readonly route = inject(ActivatedRoute);
  readonly currentUser = inject(AuthService).currentUser;
  readonly section = signal<'users' | 'services' | 'logs'>('users');
  readonly users = signal<User[]>([]);
  readonly services = signal<ServiceItem[]>([]);
  readonly logs = signal<AuditLog[]>([]);
  readonly userQuery = signal('');
  readonly userStatus = signal<'all' | 'active' | 'inactive'>('all');
  readonly serviceQuery = signal('');
  readonly serviceStatus = signal<'all' | 'active' | 'inactive'>('all');
  readonly logQuery = signal('');
  readonly logAction = signal('all');
  readonly showUserModal = signal(false);
  readonly showServiceModal = signal(false);
  readonly loading = signal(true);
  readonly message = signal('');
  readonly error = signal('');
  readonly userForm = this.fb.nonNullable.group({
    username: ['', [Validators.required, Validators.minLength(3)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });
  readonly serviceForm = this.fb.nonNullable.group({ name: ['', Validators.required] });
  readonly filteredUsers = computed(() => {
    const query = this.userQuery().trim().toLowerCase();
    return this.users().filter((user) =>
      (!query || (user.username + ' ' + user.email).toLowerCase().includes(query)) &&
      (this.userStatus() === 'all' || (this.userStatus() === 'active' ? user.is_active : !user.is_active))
    );
  });
  readonly filteredServices = computed(() => {
    const query = this.serviceQuery().trim().toLowerCase();
    return this.services().filter((service) =>
      (!query || service.name.toLowerCase().includes(query)) &&
      (this.serviceStatus() === 'all' || (this.serviceStatus() === 'active' ? service.is_active : !service.is_active))
    );
  });
  readonly filteredLogs = computed(() => {
    const query = this.logQuery().trim().toLowerCase();
    return this.logs().filter((log) =>
      (this.logAction() === 'all' || log.action === this.logAction()) &&
      (!query || ((log.username ?? '') + ' ' + log.description + ' ' + this.actionLabel(log.action)).toLowerCase().includes(query))
    );
  });

  ngOnInit(): void {
    const routeSection = this.route.snapshot.data['section'];
    if (routeSection === 'users' || routeSection === 'services' || routeSection === 'logs') {
      this.section.set(routeSection);
    }
    this.loadAll();
  }
  select(section: 'users' | 'services' | 'logs'): void {
    this.section.set(section);
  }
  openUserModal(): void {
    this.userForm.reset();
    this.showUserModal.set(true);
  }
  closeUserModal(): void {
    this.showUserModal.set(false);
    this.userForm.reset();
  }
  openServiceModal(): void {
    this.serviceForm.reset();
    this.showServiceModal.set(true);
  }
  closeServiceModal(): void {
    this.showServiceModal.set(false);
    this.serviceForm.reset();
  }
  loadAll(): void {
    this.loading.set(true);
    this.error.set('');
    this.admin
      .getUsers()
      .subscribe({
        next: (v) => this.users.set(v),
        error: (e) => this.error.set(this.apiError(e)),
      });
    this.admin
      .getServices()
      .subscribe({
        next: (v) => this.services.set(v),
        error: (e) => this.error.set(this.apiError(e)),
      });
    this.admin.getAuditLogs().subscribe({
      next: (v) => {
        this.logs.set(v);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(this.apiError(e));
        this.loading.set(false);
      },
    });
  }
  createUser(): void {
    if (this.userForm.invalid) {
      this.userForm.markAllAsTouched();
      return;
    }
    this.admin.createUser(this.userForm.getRawValue()).subscribe({
      next: (user) => {
        this.users.update((v) => [user, ...v]);
        this.closeUserModal();
        this.flash('Archiviste créé avec succès.');
      },
      error: (e) => this.error.set(this.apiError(e)),
    });
  }
  toggleUser(user: User): void {
    this.admin
      .updateUserStatus(user.id, !user.is_active)
      .subscribe({
        next: (updated) =>
          this.users.update((v) => v.map((item) => (item.id === updated.id ? updated : item))),
        error: (e) => this.error.set(this.apiError(e)),
      });
  }
  createService(): void {
    if (this.serviceForm.invalid) {
      this.serviceForm.markAllAsTouched();
      return;
    }
    this.admin.createService(this.serviceForm.controls.name.value).subscribe({
      next: (service) => {
        this.services.update((v) => [...v, service].sort((a, b) => a.name.localeCompare(b.name)));
        this.closeServiceModal();
        this.flash('Service ajouté avec succès.');
      },
      error: (e) => this.error.set(this.apiError(e)),
    });
  }
  toggleService(service: ServiceItem): void {
    this.admin
      .updateServiceStatus(service.id, !service.is_active)
      .subscribe({
        next: (updated) =>
          this.services.update((v) => v.map((item) => (item.id === updated.id ? updated : item))),
        error: (e) => this.error.set(this.apiError(e)),
      });
  }
  actionLabel(action: string): string {
    return (
      (
        {
          DOCUMENT_ARCHIVED: 'Document archivé',
          DOCUMENT_ARCHIVE_UPDATED: 'Document modifié',
          DOCUMENT_PROCESSING_RESUMED: 'Traitement relancé',
          DOCUMENT_DELETED: 'Document supprimé',
          DOCUMENT_RESTORED: 'Document restauré',
          USER_CREATED: 'Utilisateur créé',
          USER_STATUS_CHANGED: 'Statut utilisateur modifié',
          SERVICE_CREATED: 'Service créé',
          SERVICE_STATUS_CHANGED: 'Statut service modifié',
        } as Record<string, string>
      )[action] ?? 'Action système'
    );
  }

  actionBadgeClass(action: string): string {
    if (action === 'DOCUMENT_ARCHIVED' || action === 'DOCUMENT_RESTORED' || action.endsWith('_CREATED')) return 'app-badge app-badge-success';
    if (action === 'DOCUMENT_DELETED') return 'app-badge app-badge-error';
    if (action === 'DOCUMENT_PROCESSING_RESUMED') return 'app-badge app-badge-processing';
    if (action.endsWith('_STATUS_CHANGED')) return 'app-badge app-badge-warning';
    if (action.endsWith('_UPDATED')) return 'app-badge app-badge-info';
    return 'app-badge app-badge-neutral';
  }

  entityLabel(entityType: string): string {
    return ({
      DOCUMENT: 'Document',
      USER: 'Utilisateur',
      SERVICE: 'Service',
      HOSPITALIZATION: 'Hospitalisation',
      PATIENT: 'Patient',
    } as Record<string, string>)[entityType.toUpperCase()] ?? 'Élément système';
  }

  shortId(id: string | null): string {
    return id ? id.slice(0, 8) : '';
  }
  private flash(text: string): void {
    this.message.set(text);
    this.error.set('');
    setTimeout(() => this.message.set(''), 3500);
  }
  private apiError(error: { error?: { detail?: string } }): string {
    return error.error?.detail ?? 'Une erreur est survenue. Vérifiez vos droits ou réessayez.';
  }
}
