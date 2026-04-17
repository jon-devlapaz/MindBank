package embedder

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"
)

// Client talks to Ollama's embedding API.
type Client struct {
	baseURL    string
	model      string
	httpClient *http.Client
}

// NewClient creates an Ollama embedding client.
func NewClient(baseURL, model string) *Client {
	return &Client{
		baseURL: baseURL,
		model:   model,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

type embedRequest struct {
	Model  string `json:"model"`
	Prompt string `json:"prompt"`
}

type embedResponse struct {
	Embedding []float32 `json:"embedding"`
}

// Embed generates a vector embedding for the given text.
func (c *Client) Embed(ctx context.Context, text string) ([]float32, error) {
	if text == "" {
		return nil, fmt.Errorf("empty text")
	}

	body, _ := json.Marshal(embedRequest{
		Model:  c.model,
		Prompt: text,
	})

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/api/embeddings", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ollama request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("ollama status %d: %s", resp.StatusCode, string(respBody))
	}

	var result embedResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	if len(result.Embedding) == 0 {
		return nil, fmt.Errorf("empty embedding returned")
	}

	return result.Embedding, nil
}

// EmbedBatch generates embeddings for multiple texts sequentially.
func (c *Client) EmbedBatch(ctx context.Context, texts []string) ([][]float32, error) {
	results := make([][]float32, len(texts))
	for i, text := range texts {
		emb, err := c.Embed(ctx, text)
		if err != nil {
			slog.Warn("embedding failed", "index", i, "error", err)
			return nil, fmt.Errorf("embed[%d]: %w", i, err)
		}
		results[i] = emb
	}
	return results, nil
}

// Health checks if Ollama is reachable and the model is available.
func (c *Client) Health(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, "GET", c.baseURL+"/api/tags", nil)
	if err != nil {
		return err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("ollama unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("ollama status %d", resp.StatusCode)
	}
	return nil
}
