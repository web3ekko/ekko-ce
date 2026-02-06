/**
 * HTTP Client
 * 
 * Centralized HTTP client with authentication, error handling, and retries
 */

import { 
  API_CONFIG, 
  buildApiUrl, 
  HTTP_METHODS, 
  CONTENT_TYPES,
  type ApiResponse,
  type ApiError,
  type RequestConfig 
} from '../config/api'

// Token storage
const TOKEN_KEY = 'ekko-auth-token'

class HttpClient {
  private baseURL: string
  private timeout: number
  private retryAttempts: number
  private retryDelay: number

  constructor() {
    this.baseURL = API_CONFIG.BASE_URL
    this.timeout = API_CONFIG.TIMEOUT
    this.retryAttempts = API_CONFIG.RETRY_ATTEMPTS
    this.retryDelay = API_CONFIG.RETRY_DELAY
  }

  // Get stored auth token
  private getAuthToken(): string | null {
    return localStorage.getItem(TOKEN_KEY)
  }

  // Set auth token
  setAuthToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token)
  }

  // Clear auth token
  clearAuthToken(): void {
    localStorage.removeItem(TOKEN_KEY)
  }

  // Build headers
  private buildHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': CONTENT_TYPES.JSON,
      ...customHeaders,
    }

    const token = this.getAuthToken()
    if (token) {
      headers['Authorization'] = `Token ${token}`
    }

    return headers
  }

  // Handle API errors
  private handleError(error: any, url: string, method: string): ApiError {
    // Log error internally without exposing to console

    if (error.name === 'AbortError') {
      return {
        message: 'Request was cancelled',
        status: 0,
        code: 'REQUEST_CANCELLED'
      }
    }

    if (!error.response) {
      return {
        message: 'Network error - please check your connection',
        status: 0,
        code: 'NETWORK_ERROR'
      }
    }

    const status = error.response.status || 500
    let message = 'An unexpected error occurred'

    if (error.response.data) {
      if (typeof error.response.data === 'string') {
        message = error.response.data
      } else if (error.response.data.message) {
        message = error.response.data.message
      } else if (error.response.data.detail) {
        message = error.response.data.detail
      } else if (error.response.data.error) {
        message = error.response.data.error
      }
    }

    // Handle specific status codes
    switch (status) {
      case 401: {
        // Only clear token for certain endpoints to avoid clearing during signup flow
        const shouldClearToken = !url.includes('/signup/') && !url.includes('/verify-code/')
        if (shouldClearToken) {
          this.clearAuthToken()
          // Dispatch event for app to handle session expiry and redirect
          window.dispatchEvent(new CustomEvent('auth:session-expired'))
        }
        message = 'Authentication required - please log in again'
        break
      }
      case 403:
        message = 'Access denied - insufficient permissions'
        break
      case 404:
        message = 'Resource not found'
        break
      case 422:
        message = 'Validation error - please check your input'
        break
      case 429:
        message = 'Too many requests - please try again later'
        break
      case 500:
        message = 'Server error - please try again later'
        break
    }

    return {
      message,
      status,
      code: error.response.data?.code,
      details: error.response.data?.details
    }
  }

  // Sleep utility for retries
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  // Make HTTP request with retries
  private async makeRequest<T>(config: RequestConfig): Promise<ApiResponse<T>> {
    const { url, method, headers = {}, data, params, timeout = this.timeout } = config
    const fullUrl = buildApiUrl(url)
    
    let lastError: any

    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), timeout)

        // Build request options
        const builtHeaders = this.buildHeaders(headers)
        const requestOptions: RequestInit = {
          method,
          headers: builtHeaders,
          signal: controller.signal,
          credentials: 'include', // Include cookies for session management
        }

        // Add body for non-GET requests
        if (method !== HTTP_METHODS.GET && data) {
          if (builtHeaders['Content-Type'] === CONTENT_TYPES.JSON) {
            requestOptions.body = JSON.stringify(data)
          } else {
            requestOptions.body = data
          }
        }

        // Add query parameters
        let requestUrl = fullUrl
        if (params && Object.keys(params).length > 0) {
          const searchParams = new URLSearchParams()
          Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
              searchParams.append(key, String(value))
            }
          })
          requestUrl += `?${searchParams.toString()}`
        }


        const response = await fetch(requestUrl, requestOptions)
        clearTimeout(timeoutId)

        let responseData: any
        const contentType = response.headers.get('content-type')
        
        if (contentType && contentType.includes('application/json')) {
          responseData = await response.json()
        } else {
          responseData = await response.text()
        }

        if (!response.ok) {
          throw {
            response: {
              status: response.status,
              data: responseData
            }
          }
        }


        return {
          data: responseData,
          status: response.status,
          success: true,
          message: responseData?.message
        }

      } catch (error) {
        lastError = error
        
        // Don't retry on certain errors (client errors and auth errors)
        if (error.response?.status === 400 || error.response?.status === 401 ||
            error.response?.status === 403 || error.response?.status === 404) {
          break
        }

        // Don't retry on last attempt
        if (attempt === this.retryAttempts) {
          break
        }

        // Retry silently
        await this.sleep(this.retryDelay * attempt) // Exponential backoff
      }
    }

    throw this.handleError(lastError, url, method)
  }

  // HTTP Methods
  async get<T>(url: string, params?: Record<string, any>, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.makeRequest<T>({
      url,
      method: HTTP_METHODS.GET,
      params,
      headers
    })
  }

  async post<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.makeRequest<T>({
      url,
      method: HTTP_METHODS.POST,
      data,
      headers
    })
  }

  async put<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.makeRequest<T>({
      url,
      method: HTTP_METHODS.PUT,
      data,
      headers
    })
  }

  async patch<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.makeRequest<T>({
      url,
      method: HTTP_METHODS.PATCH,
      data,
      headers
    })
  }

  async delete<T>(url: string, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.makeRequest<T>({
      url,
      method: HTTP_METHODS.DELETE,
      headers
    })
  }
}

// Export singleton instance
export const httpClient = new HttpClient()
export default httpClient
