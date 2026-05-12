import { useRouter } from 'next/router';
import { useState } from 'react';
import Typing from '@/components/Typing';

export default function Home() {
  const router = useRouter();
  const [showAbout, setShowAbout] = useState(false);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center text-gray-800 px-6" style={{ background: 'linear-gradient(135deg, #f3e8ff 0%, #eff6ff 50%, #e0e7ff 100%)' }}>
      <div className="text-center mb-10">
        <Typing text={"Welcome to Warith's K-pop Predictor!"} />
      </div>

      <div className="flex gap-4">
        <button
          className="px-8 py-4 text-white rounded-full hover:scale-105 transition transform shadow-lg hover:shadow-xl font-semibold"
          style={{ background: 'linear-gradient(to right, #a855f7, #3b82f6)' }}
          onClick={() => router.push('/gen')}
        >
          Get Started
        </button>

        <button
          className="px-8 py-4 text-white rounded-full hover:scale-105 transition transform shadow-lg hover:shadow-xl font-semibold"
          style={{ background: 'linear-gradient(to right, #6b7280, #4b5563)' }}
          onClick={() => setShowAbout(true)}
        >
          About
        </button>
      </div>

      {showAbout && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full shadow-xl">
            <h2 className="text-2xl font-semibold mb-4 text-gray-800">About K-pop Predictor</h2>
            <p className="text-gray-600 mb-4">
              This project uses machine learning to predict when K-pop groups will release their next album, EP, or single based on their historical release patterns.
            </p>
            <p className="text-gray-600 mb-4">
              Select a generation (4th or 5th gen), choose your favorite group, and get an AI-powered prediction of their next release date!
            </p>
            <div className="flex justify-end">
              <button
                className="px-4 py-2 text-white rounded hover:opacity-90 transition"
                style={{ backgroundColor: '#a855f7' }}
                onClick={() => setShowAbout(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
