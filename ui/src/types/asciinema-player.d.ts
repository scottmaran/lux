declare module 'asciinema-player' {
  export function create(
    src: string,
    container: HTMLElement,
    options?: Record<string, unknown>
  ): any;
}
