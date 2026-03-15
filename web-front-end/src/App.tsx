import AnimatedRoutes from './components/AnimatedRoutes';
import CustomCursor from './components/CustomCursor';

/**
 * / = gate; /home = home; /request-access = form. All other paths → /.
 * Home and request-access use a subtle slide + fade transition (Framer Motion).
 */
function App() {
  return (
    <>
      <CustomCursor />
      <AnimatedRoutes />
    </>
  );
}

export default App;
