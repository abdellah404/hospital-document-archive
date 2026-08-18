import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { User } from '../models/user';
import { environment } from '../../../environments/environment';


interface LoginRequest {
  username: string;
  password: string;
}

interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private http = inject(HttpClient);

  private apiUrl = environment.apiUrl;

  readonly currentUser = signal<User | null>(null);

  login(data: LoginRequest): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(
        `${this.apiUrl}/auth/login`,
        data
      )
      .pipe(
        tap((response) => {
          localStorage.setItem(
            'access_token',
            response.access_token
          );
          this.getCurrentUser().subscribe({ next: user => this.currentUser.set(user) });
        })
      );
  }

  register(data: RegisterRequest): Observable<User> {
    return this.http.post<User>(
      `${this.apiUrl}/auth/register`,
      data
    );
  }

  getCurrentUser(): Observable<User> {
    return this.http.get<User>(
      `${this.apiUrl}/auth/me`
    ).pipe(tap(user => this.currentUser.set(user)));
  }

  isAdmin(): boolean {
    return this.currentUser()?.role === 'ADMIN';
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  logout(): void {
    localStorage.removeItem('access_token');
    this.currentUser.set(null);
  }
}
