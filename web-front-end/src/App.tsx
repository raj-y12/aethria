import AnimatedRoutes from './components/AnimatedRoutes';

/**
 * / = gate; /home = home (the application form lives at /home#access).
 * /request-access redirects to /home#access for old links. All other paths → /.
 */
function App() {
  return <AnimatedRoutes />;
}

export default App;
