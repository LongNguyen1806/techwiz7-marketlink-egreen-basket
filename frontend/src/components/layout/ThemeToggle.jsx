import { Moon, Sun } from 'lucide-react';
import { Button } from '../ui/Button';
import { useUiStore } from '../../stores/ui.store';
import '../../styles/common/ThemeToggle.css';

export function ThemeToggle() {
  const theme = useUiStore((state) => state.theme);
  const toggleTheme = useUiStore((state) => state.toggleTheme);
  const isDark = theme === 'dark';

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={toggleTheme}
    >
      {isDark ? <Sun className="theme-toggle__icon" /> : <Moon className="theme-toggle__icon" />}
    </Button>
  );
}
