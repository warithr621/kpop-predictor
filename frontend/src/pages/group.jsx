import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { fetchGroups, fetchReleases, postPredict } from '@/lib/api';
import Timeline from '@/components/Timeline';

export default function GroupPage() {
  const router = useRouter();
  const { name } = router.query;
  const [meta, setMeta] = useState(null);
  const [releases, setReleases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!name) return;
    fetchGroups().then((gs) => {
      const found = gs.find((g) => g.name === name);
      setMeta(found || { name });
    });
    fetchReleases(name).then(setReleases).catch((e) => setError(e.message));
  }, [name]);

  const onPredict = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await postPredict(name);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const pretty = useMemo(() => {
    if (!result) return '';
    const d = new Date(result.pred_date);
    const dateStr = d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
    return `Model predicts next release around ${dateStr}`;
  }, [result]);

  return (
    <main className="min-h-screen bg-gradient-to-br from-purple-50 via-blue-50 to-indigo-50 text-gray-800 p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div>
              <div className="text-3xl font-bold text-gray-800">{meta?.name}</div>
              <div className="text-lg text-gray-600">
                {meta?.company && <span className="mr-2">{meta.company}</span>}
                {meta?.generation && <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">{meta.generation}</span>}
              </div>
            </div>
          </div>
          <button onClick={() => router.back()} className="text-sm text-gray-600 hover:text-gray-800 bg-white px-3 py-1 rounded shadow">Back</button>
        </div>

        <div className="bg-white rounded-lg p-6 mb-6 shadow-lg">
          <Timeline releases={releases} />
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={onPredict}
            disabled={loading}
            className="px-6 py-3 rounded-md bg-gradient-to-r from-purple-500 to-blue-500 text-white disabled:opacity-60 shadow-lg hover:shadow-xl transition"
          >
            {loading ? 'Predicting…' : `Predict ${meta?.name || ''}'s next release`}
          </button>
          {error && <div className="text-red-500 text-sm bg-white p-2 rounded shadow">{error}</div>}
        </div>

        {result && (
          <div className="mt-6 bg-white rounded-lg p-6 shadow-lg">
            <div className="text-lg text-gray-800">{pretty}</div>
            {result.metrics && (
              <div className="text-sm text-gray-600 mt-2">
                Past MAE: {result.metrics.mae_days ? `${Math.round(result.metrics.mae_days)} days` : 'n/a'}
                {result.metrics.mape_pct ? ` • MAPE: ${result.metrics.mape_pct.toFixed(1)}%` : ''}
              </div>
            )}
            <div className="mt-4 flex gap-3">
              <a
                href={`data:text/json,${encodeURIComponent(JSON.stringify(result, null, 2))}`}
                download={`${meta?.name || 'prediction'}.json`}
                className="text-sm text-purple-600 hover:text-purple-800 underline"
              >Download JSON</a>
              <a
                href={`data:text/csv,${encodeURIComponent(`group,pred_date,uncertainty_days\n${meta?.name},${result.pred_date},${result.uncertainty_days || ''}`)}`}
                download={`${meta?.name || 'prediction'}.csv`}
                className="text-sm text-purple-600 hover:text-purple-800 underline"
              >Download CSV</a>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

