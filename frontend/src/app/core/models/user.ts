

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  must_change_password: boolean;
}
