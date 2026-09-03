import { Component, inject } from '@angular/core';
import {
  FormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';

import { AuthService } from '../../../core/services/auth';

@Component({
  selector: 'app-change-password',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './change-password.html',
  styleUrl: './change-password.css',
})
export class ChangePasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  readonly user = this.authService.currentUser;
  errorMessage = '';
  isSubmitting = false;

  readonly form = this.fb.nonNullable.group({
    currentPassword: ['', Validators.required],
    newPassword: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128)]],
    confirmPassword: ['', Validators.required],
  });

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const { currentPassword, newPassword, confirmPassword } = this.form.getRawValue();

    if (newPassword !== confirmPassword) {
      this.errorMessage = 'Les nouveaux mots de passe ne correspondent pas.';
      return;
    }

    this.errorMessage = '';
    this.isSubmitting = true;

    this.authService.changePassword({
      current_password: currentPassword,
      new_password: newPassword,
    }).pipe(
      finalize(() => (this.isSubmitting = false))
    ).subscribe({
      next: () => {
        void this.router.navigate(['/dashboard']);
      },
      error: (error) => {
        this.errorMessage = this.errorText(error.error?.detail);
      },
    });
  }

  logout(): void {
    this.authService.logout();
    void this.router.navigate(['/login']);
  }

  private errorText(detail?: string): string {
    if (detail === 'Current password is incorrect') {
      return 'Le mot de passe actuel est incorrect.';
    }

    if (detail === 'New password must be different from current password') {
      return 'Le nouveau mot de passe doit être différent du mot de passe actuel.';
    }

    return detail ?? 'Impossible de modifier le mot de passe. Veuillez réessayer.';
  }
}
