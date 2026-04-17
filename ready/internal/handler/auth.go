package handler

import (
	"net/http"
	"os"
	"strings"
)

// APIKeyAuth returns middleware that validates API key from Authorization header.
// If MB_API_KEY is not set, auth is disabled (dev mode).
func APIKeyAuth(next http.Handler) http.Handler {
	expectedKey := os.Getenv("MB_API_KEY")
	if expectedKey == "" {
		return next // No key set — auth disabled (dev mode)
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Allow health check without auth
		if r.URL.Path == "/api/v1/health" {
			next.ServeHTTP(w, r)
			return
		}

		auth := r.Header.Get("Authorization")
		if auth == "" {
			respondError(w, 401, "missing Authorization header")
			return
		}

		// Support "Bearer <key>" or just "<key>"
		key := strings.TrimPrefix(auth, "Bearer ")
		if key != expectedKey {
			respondError(w, 401, "invalid API key")
			return
		}

		next.ServeHTTP(w, r)
	})
}
