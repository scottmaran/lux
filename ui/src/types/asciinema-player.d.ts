declare module 'asciinema-player' {
  const AsciinemaPlayer: {
    create: (src: string, container: HTMLElement, options?: Record<string, unknown>) => any;
  };
  export default AsciinemaPlayer;
}
