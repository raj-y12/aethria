/**
 * Deal Flow Terminal — Main Header (80px)
 * Aethria with 1px underline, 40px width, centered.
 */
export default function DealFlowHeader() {
  return (
    <header
      className="fixed left-0 right-0 z-40 h-20 flex items-center justify-center bg-paper-cream border-b border-steel-gray/20"
      style={{ top: '32px', borderWidth: '0.5px' }}
    >
      <a href="/" className="flex flex-col items-center" aria-label="Aethria">
        <span className="font-display font-medium text-oxford text-2xl tracking-tight">
          Aethria
        </span>
        <span
          className="mt-1 w-10 border-b border-oxford"
          style={{ borderWidth: '1px' }}
          aria-hidden
        />
      </a>
    </header>
  );
}
