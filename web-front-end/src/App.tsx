import AnimatedRoutes from './components/AnimatedRoutes';

/**
 * / = gate; /home = home; /request-access = form. All other paths → /.
 * Home and request-access use a subtle slide + fade transition (Framer Motion).
 */
function App() {
  return <AnimatedRoutes />;
}

export default App;
