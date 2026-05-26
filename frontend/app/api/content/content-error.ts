export class ContentServiceError extends Error {
  constructor(
    message: string,
    readonly status = 500,
  ) {
    super(message);
  }
}
