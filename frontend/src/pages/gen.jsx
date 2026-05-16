import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function GenRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace('/'); }, []);
  return null;
}
