// A stand in for `lightweight-charts`, mocked for every test in `setup.ts`: jsdom has no canvas,
// so the real library cannot draw. It records what the equity chart asked for, so tests can
// check the lines, their data and the OOS marker.
export interface FakeSeries {
  options: Record<string, unknown>;
  data: { time: string; value: number }[];
  markers: { time: string; text?: string; color?: string }[];
}

export interface FakeChart {
  options: Record<string, unknown>;
  series: FakeSeries[];
  removed: boolean;
}

export const charts: FakeChart[] = [];

export const LineSeries = { type: "Line" };

export function createChart(_element: HTMLElement, options: Record<string, unknown>) {
  const chart: FakeChart = { options, series: [], removed: false };
  charts.push(chart);
  return {
    addSeries(_definition: unknown, seriesOptions: Record<string, unknown>) {
      const series: FakeSeries = { options: { ...seriesOptions }, data: [], markers: [] };
      chart.series.push(series);
      return {
        fake: series,
        setData(data: FakeSeries["data"]) {
          series.data = data;
        },
        applyOptions(next: Record<string, unknown>) {
          Object.assign(series.options, next);
        },
      };
    },
    applyOptions(next: Record<string, unknown>) {
      Object.assign(chart.options, next);
    },
    timeScale: () => ({ fitContent() {} }),
    remove() {
      chart.removed = true;
    },
  };
}

export function createSeriesMarkers(series: { fake: FakeSeries }) {
  return {
    setMarkers(markers: FakeSeries["markers"]) {
      series.fake.markers = markers;
    },
  };
}
