import { useState, useRef, useMemo, useCallback } from 'react';
import { parsePipelineCsv } from '../utils/parsePipelineCsv';

/**
 * Hook that manages runtime CSV upload for swapping pipeline recommendations.
 *
 * @param {Array} baseDataset - The original golden_dataset.json array
 * @returns {{ dataset, uploadState, triggerUpload, clearUpload }}
 */
export function useCsvUpload(baseDataset) {
  const catalogImagesRef = useRef(null);
  const [pendingMap, setPendingMap] = useState(null);
  const [overrideMap, setOverrideMap] = useState(null);
  const [uploadState, setUploadState] = useState({
    status: 'idle', // 'idle' | 'loading' | 'parsed' | 'applied' | 'error'
    filename: null,
    matchedCount: 0,
    totalCsvProducts: 0,
    error: null,
  });

  // Build a productInfoLookup from the base dataset (for enriching CSV recs with names/URLs)
  const productInfoLookup = useMemo(() => {
    const lookup = new Map();
    for (const record of baseDataset) {
      lookup.set(record.source_product_id, {
        product_name: record.source_product_name,
        product_url: record.source_product_url,
      });
      for (const rp of record.recommended_products) {
        if (!lookup.has(rp.product_id)) {
          lookup.set(rp.product_id, {
            product_name: rp.product_name,
            product_url: rp.product_url,
          });
        }
      }
    }
    return lookup;
  }, [baseDataset]);

  // Derive the effective dataset by overlaying overrideMap onto baseDataset
  const dataset = useMemo(() => {
    if (!overrideMap) return baseDataset;
    return baseDataset.map(record => {
      const override = overrideMap.get(record.source_product_id);
      if (!override) return record;
      return { ...record, pipeline_recommendations: override };
    });
  }, [baseDataset, overrideMap]);

  const handleFile = useCallback((file) => {
    setUploadState({
      status: 'loading',
      filename: file.name,
      matchedCount: 0,
      totalCsvProducts: 0,
      error: null,
    });

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        // Lazy-load catalog images on first upload (code-split by Vite)
        if (!catalogImagesRef.current) {
          const mod = await import('../data/catalog_image_lookup.json');
          catalogImagesRef.current = mod.default;
        }

        const { recommendations, totalCsvProducts } = parsePipelineCsv(
          e.target.result,
          catalogImagesRef.current,
          productInfoLookup,
        );

        // Count how many CSV products match the golden dataset
        const datasetIds = new Set(baseDataset.map(r => r.source_product_id));
        let matchedCount = 0;
        for (const pid of recommendations.keys()) {
          if (datasetIds.has(pid)) matchedCount++;
        }

        setPendingMap(recommendations);
        setUploadState({
          status: 'parsed',
          filename: file.name,
          matchedCount,
          totalCsvProducts,
          error: null,
        });
      } catch (err) {
        setUploadState({
          status: 'error',
          filename: file.name,
          matchedCount: 0,
          totalCsvProducts: 0,
          error: err.message,
        });
      }
    };
    reader.onerror = () => {
      setUploadState({
        status: 'error',
        filename: file.name,
        matchedCount: 0,
        totalCsvProducts: 0,
        error: 'Failed to read file',
      });
    };
    reader.readAsText(file);
  }, [baseDataset, productInfoLookup]);

  const triggerUpload = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv';
    input.onchange = (e) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    };
    input.click();
  }, [handleFile]);

  const applyUpload = useCallback(() => {
    if (!pendingMap) return;
    setOverrideMap(pendingMap);
    setPendingMap(null);
    setUploadState(prev => ({ ...prev, status: 'applied' }));
  }, [pendingMap]);

  const clearUpload = useCallback(() => {
    setPendingMap(null);
    setOverrideMap(null);
    setUploadState({
      status: 'idle',
      filename: null,
      matchedCount: 0,
      totalCsvProducts: 0,
      error: null,
    });
  }, []);

  return { dataset, uploadState, triggerUpload, applyUpload, clearUpload };
}
