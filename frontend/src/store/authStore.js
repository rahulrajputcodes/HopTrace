import { create } from 'zustand';

/**
 * HopTrace Auth Store (M2 Lane)
 *
 * M2-0 Stub: always signed in as 'operator' so M3 and M4 can code immediately.
 * Exact contract required:
 *   useAuth() => { user, role, isAuthenticated, login(username, password), logout() }
 */
export const useAuth = create((set) => ({
  user: 'operator',
  role: 'operator',
  token: 'stub-operator-token',
  isAuthenticated: true,

  login: async (username, password) => {
    void password;
    // Stub login: resolves immediately with operator identity
    const stubIdentity = {
      user: username || 'operator',
      role: 'operator',
      token: 'stub-operator-token',
      isAuthenticated: true,
    };
    set(stubIdentity);
    return stubIdentity;
  },

  logout: () => {
    // Stub logout: keeps operator identity in M2-0 stub mode
    set({
      user: 'operator',
      role: 'operator',
      token: 'stub-operator-token',
      isAuthenticated: true,
    });
  },
}));

export default useAuth;
