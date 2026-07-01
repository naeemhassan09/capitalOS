import { useNavigate } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <Compass className="h-12 w-12 text-muted-foreground" aria-hidden />
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Page not found</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The page you are looking for does not exist.
        </p>
      </div>
      <Button onClick={() => navigate('/')}>Back to dashboard</Button>
    </div>
  );
}
