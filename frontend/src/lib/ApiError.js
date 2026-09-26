import { CLIENT_ERROR_CODES, describeError } from '../utils/errorMap';

export class ApiError extends Error {
  constructor({ status = 0, message = '', code, fieldErrors, data, requestId } = {}) {
    super(message || 'Request failed');
    this.name = 'ApiError';
    this.status = status;
    this.code = code ?? (status === 0 ? CLIENT_ERROR_CODES.NETWORK_ERROR : CLIENT_ERROR_CODES.UNKNOWN);
    this.fieldErrors = fieldErrors ?? {};
    // The backend's own sentence. Shown only where errorMap allows it, never the code.
    this.apiMessage = message;
    this.data = data;
    // Backend request_id, quoted to support on server errors.
    this.requestId = requestId ?? null;
  }

  is(code) {
    return this.code === code;
  }

  get isNetworkError() {
    return this.code === CLIENT_ERROR_CODES.NETWORK_ERROR;
  }

  get isServerError() {
    return this.status >= 500;
  }

  get hasFieldErrors() {
    return Object.keys(this.fieldErrors).length > 0;
  }

  /** { title, description } in plain English. */
  get friendly() {
    return describeError(this);
  }

  get friendlyMessage() {
    return this.friendly.title;
  }

  static fromUnknown(error) {
    if (error instanceof ApiError) return error;
    return new ApiError({ code: CLIENT_ERROR_CODES.UNKNOWN, message: error?.message });
  }
}

export default ApiError;
