import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { User } from '../models/user';

export interface ServiceItem { id: string; name: string; is_active: boolean; }
export interface AuditLog {
  id: string; user_id: string | null; username: string | null; action: string;
  entity_type: string; entity_id: string | null; description: string;
  details: Record<string, unknown> | null; created_at: string;
}

@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  getUsers(): Observable<User[]> { return this.http.get<User[]>(`${this.apiUrl}/auth/users`); }
  createUser(data: { username: string; email: string; password: string }): Observable<User> {
    return this.http.post<User>(`${this.apiUrl}/auth/register`, data);
  }
  updateUserStatus(id: string, isActive: boolean): Observable<User> {
    return this.http.patch<User>(`${this.apiUrl}/auth/users/${id}/status`, null, {
      params: new HttpParams().set('is_active', isActive),
    });
  }

  getServices(): Observable<ServiceItem[]> { return this.http.get<ServiceItem[]>(`${this.apiUrl}/services`); }
  createService(name: string): Observable<ServiceItem> {
    return this.http.post<ServiceItem>(`${this.apiUrl}/services`, { name });
  }
  updateServiceStatus(id: string, isActive: boolean): Observable<ServiceItem> {
    return this.http.patch<ServiceItem>(`${this.apiUrl}/services/${id}/status`, null, {
      params: new HttpParams().set('is_active', isActive),
    });
  }

  getAuditLogs(page = 1, pageSize = 50): Observable<AuditLog[]> {
    return this.http.get<AuditLog[]>(`${this.apiUrl}/audit-logs`, {
      params: new HttpParams().set('page', page).set('page_size', pageSize),
    });
  }
}
