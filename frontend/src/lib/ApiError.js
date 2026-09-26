import { getErrorMessage } from '@/utils/errorMap';

export class ApiError extends Error {
  constructor({ status = 0, message = 'An error occurred', code, fieldErrors = {}, data } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors ?? {};
    this.apiMessage = message;
    this.data = data;
  }

  get friendlyMessage() {
    return getErrorMessage(this.code, this.apiMessage);
  }

  static fromUnknown(error) {
    if (error instanceof ApiError) return error;
    if (error instanceof Error) {
      return new ApiError({ status: 0, message: error.message });
    }
    return new ApiError({ status: 0, message: 'An unknown error occurred' });
  }
}

export default ApiError;
