import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Optional Java module: turns a predictions CSV into a plain-text flood report.
 *  Usage: java -cp modules/build ReportGenerator input.csv output.txt
 *  CSV columns: name,risk_level,risk_score,ponding_cm,rain_1h,rain_24h,forecast_3h */
public class ReportGenerator {
    public static void main(String[] args) throws IOException {
        if (args.length < 2) { System.err.println("usage: ReportGenerator in.csv out.txt"); System.exit(1); }
        List<String[]> rows = new ArrayList<>();
        try (BufferedReader br = Files.newBufferedReader(Paths.get(args[0]))) {
            br.readLine(); // header
            String line;
            while ((line = br.readLine()) != null) if (!line.isBlank()) rows.add(line.split(",", -1));
        }
        rows.sort((a, b) -> Double.compare(Double.parseDouble(b[2]), Double.parseDouble(a[2])));

        int low = 0, mod = 0, high = 0, severe = 0;
        for (String[] r : rows) {
            switch (r[1]) { case "Low": low++; break; case "Moderate": mod++; break;
                            case "High": high++; break; default: severe++; }
        }
        try (PrintWriter w = new PrintWriter(Files.newBufferedWriter(Paths.get(args[1])))) {
            w.println("MICRO-DRAINAGE & LOCALIZED FLOOD REPORT");
            w.println("Generated: " + new Date());
            w.println("Zones monitored: " + rows.size());
            w.printf("Low: %d | Moderate: %d | High: %d | Severe: %d%n%n", low, mod, high, severe);
            w.println(String.format("%-28s %-9s %6s %9s %8s %8s", "Zone", "Level", "Score", "Water cm", "Rain1h", "Rain24h"));
            for (String[] r : rows)
                w.println(String.format("%-28s %-9s %6s %9s %8s %8s", r[0], r[1], r[2], r[3], r[4], r[5]));
            if (high + severe > 0) {
                w.println("\nPRIORITY ZONES (High / Severe):");
                for (String[] r : rows)
                    if (r[1].equals("High") || r[1].equals("Severe"))
                        w.println(" - " + r[0] + ": possible ponding " + r[3] + " cm, " + r[6] + " mm forecast in 3 h");
            } else {
                w.println("\nNo High or Severe zones at this time.");
            }
        }
    }
}
