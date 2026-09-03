import { inject } from '@angular/core';
import {
  CanActivateFn,
  Router,
} from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { AuthService } from '../services/auth';


export const authGuard: CanActivateFn = (_route, state) => {

  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/login']);
  }

  const resolveAccess = (mustChangePassword: boolean) => {
    if (state.url.startsWith('/change-password')) {
      return true;
    }

    return mustChangePassword
      ? router.createUrlTree(['/change-password'])
      : true;
  };

  const currentUser = authService.currentUser();

  if (currentUser) {
    return resolveAccess(currentUser.must_change_password);
  }

  return authService.getCurrentUser().pipe(
    map((user) => resolveAccess(user.must_change_password)),
    catchError(() => of(router.createUrlTree(['/login'])))
  );
};
