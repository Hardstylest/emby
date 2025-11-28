import { useState, useEffect } from "react";
import "@/App.css";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Loader2, Download, Search, Film, Database, Trash2, FolderOpen, Play, Pause, Plus, X, Eye, Activity } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [activeTab, setActiveTab] = useState("scrape");
  const [source, setSource] = useState("gaydvdempire");
  const [movieId, setMovieId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [metadata, setMetadata] = useState(null);
  const [nfoContent, setNfoContent] = useState("");
  const [nfoFilename, setNfoFilename] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [savedMovies, setSavedMovies] = useState([]);
  const [loadingMovies, setLoadingMovies] = useState(false);
  const [outputFilePath, setOutputFilePath] = useState("");
  
  // Monitor state
  const [monitorStatus, setMonitorStatus] = useState(null);
  const [newFolderPath, setNewFolderPath] = useState("");
  const [scanResults, setScanResults] = useState([]);
  const [processedFiles, setProcessedFiles] = useState([]);
  const [loadingMonitor, setLoadingMonitor] = useState(false);
  
  // System info state
  const [systemInfo, setSystemInfo] = useState(null);
  const [systemLogs, setSystemLogs] = useState({ backend: '', frontend: '' });
  const [loadingSystemInfo, setLoadingSystemInfo] = useState(false);
  const [restartingBackend, setRestartingBackend] = useState(false);


  // Load saved paths from localStorage on mount
  useEffect(() => {
    const savedOutputPath = localStorage.getItem('outputFilePath');
    if (savedOutputPath) {
      setOutputFilePath(savedOutputPath);
    }
    
    const savedMonitorPath = localStorage.getItem('lastMonitorPath');
    if (savedMonitorPath) {
      setNewFolderPath(savedMonitorPath);
    }
  }, []);

  // Save output path to localStorage when it changes
  useEffect(() => {
    if (outputFilePath) {
      localStorage.setItem('outputFilePath', outputFilePath);
    }
  }, [outputFilePath]);

  useEffect(() => {
    if (activeTab === "history") {
      loadSavedMovies();
    } else if (activeTab === "monitor") {
      loadMonitorStatus();
      loadProcessedFiles();
    }
  }, [activeTab]);

  const loadSavedMovies = async () => {
    setLoadingMovies(true);
    try {
      const response = await axios.get(`${API}/movies`);
      setSavedMovies(response.data);
    } catch (error) {
      console.error("Error loading movies:", error);
      toast.error("Failed to load saved movies");
    } finally {
      setLoadingMovies(false);
    }
  };

  const handleScrape = async () => {
    if (!movieId.trim()) {
      toast.error("Please enter a movie ID or URL");
      return;
    }

    setLoading(true);
    setMetadata(null);
    setNfoContent("");
    setNfoFilename("");

    try {
      // Extract ID from URL if a full URL is provided
      let extractedId = movieId.trim();
      
      // Check if it's a URL
      if (extractedId.includes('http') || extractedId.includes('www.')) {
        // Extract ID based on source
        if (source === 'gaydvdempire') {
          // Pattern: https://www.gaydvdempire.com/5026246/ or /5026246/title.html
          const match = extractedId.match(/\/(\d+)\/?/);
          if (match) {
            extractedId = match[1];
            toast.info(`Extracted ID: ${extractedId}`);
          }
        } else if (source === 'aebn') {
          // Pattern for AEBN URLs
          const match = extractedId.match(/\/(\d+)\/?/);
          if (match) {
            extractedId = match[1];
            toast.info(`Extracted ID: ${extractedId}`);
          }
        } else if (source === 'gevi') {
          // Pattern for GEVI URLs
          const match = extractedId.match(/\/([^\/]+)$/);
          if (match) {
            extractedId = match[1].replace('.html', '');
            toast.info(`Extracted ID: ${extractedId}`);
          }
        }
      }

      const response = await axios.post(`${API}/scrape`, {
        source: source,
        movie_id: extractedId
      });

      setMetadata(response.data);
      toast.success(`Successfully scraped metadata from ${source}`);
      
      // Auto-generate NFO with optional output path for image download
      const nfoPayload = {
        metadata: response.data
      };
      
      // Add output_path if provided (for automatic image download)
      if (outputFilePath.trim()) {
        nfoPayload.output_path = outputFilePath.trim();
      }
      
      const nfoResponse = await axios.post(`${API}/generate-nfo`, nfoPayload);
      
      setNfoContent(nfoResponse.data.nfo_content);
      setNfoFilename(nfoResponse.data.filename); // Save the filename from backend
      
      // Show success messages
      let successMessage = "Metadata scraped successfully!";
      
      if (nfoResponse.data.nfo_saved) {
        successMessage = `✅ NFO saved: ${nfoResponse.data.filename}`;
        toast.success(successMessage, { duration: 5000 });
      }
      
      if (nfoResponse.data.images_downloaded && nfoResponse.data.images_downloaded.length > 0) {
        toast.success(`✅ ${nfoResponse.data.images_downloaded.length} image(s) downloaded!`, { duration: 5000 });
      }
      
      // If files were auto-saved, show a comprehensive success message
      if (nfoResponse.data.nfo_saved && nfoResponse.data.images_downloaded?.length > 0) {
        toast.success(`🎉 Complete! NFO + ${nfoResponse.data.images_downloaded.length} image(s) saved automatically!`, { duration: 7000 });
      }
    } catch (error) {
      console.error("Scraping error:", error);
      toast.error(error.response?.data?.detail || "Failed to scrape metadata");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      toast.error("Please enter a search query");
      return;
    }

    setLoading(true);
    setSearchResults([]);

    try {
      const response = await axios.post(`${API}/search`, {
        source: source,
        query: searchQuery.trim()
      });

      setSearchResults(response.data.results || []);
      
      if (response.data.results && response.data.results.length > 0) {
        toast.success(`Found ${response.data.results.length} results`);
      } else {
        toast.info(response.data.message || "No results found");
      }
    } catch (error) {
      console.error("Search error:", error);
      toast.error("Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadNFO = () => {
    if (!nfoContent) {
      toast.error("No NFO content to download");
      return;
    }

    const blob = new Blob([nfoContent], { type: 'text/xml' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    // Use the filename from backend (includes year if available), fallback to title-based name
    a.download = nfoFilename || `${metadata?.title?.replace(/[/\\?%*:|"<>]/g, '-') || 'movie'}.nfo`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    toast.success("NFO file downloaded");
  };

  const handleDeleteMovie = async (movieId) => {
    try {
      await axios.delete(`${API}/movies/${movieId}`);
      toast.success("Movie deleted");
      loadSavedMovies();
    } catch (error) {
      console.error("Delete error:", error);
      toast.error("Failed to delete movie");
    }
  };

  const handleSelectSearchResult = (result) => {
    if (result.id) {
      setMovieId(result.id);
      setActiveTab("scrape");
      toast.success("Movie ID set. Click 'Scrape Metadata' to fetch details.");
    }
  };

  // Monitor Functions
  const loadMonitorStatus = async () => {
    try {
      const response = await axios.get(`${API}/monitor/status`);
      setMonitorStatus(response.data);
    } catch (error) {
      console.error("Error loading monitor status:", error);
      toast.error("Failed to load monitor status");
    }
  };

  const loadProcessedFiles = async () => {
    try {
      const response = await axios.get(`${API}/monitor/processed-files`);
      setProcessedFiles(response.data.files || []);
    } catch (error) {
      console.error("Error loading processed files:", error);
    }
  };

  const handleStartMonitoring = async () => {
    setLoadingMonitor(true);
    try {
      await axios.post(`${API}/monitor/start`);
      toast.success("Folder monitoring started");
      await loadMonitorStatus();
    } catch (error) {
      console.error("Error starting monitor:", error);
      toast.error("Failed to start monitoring");
    } finally {
      setLoadingMonitor(false);
    }
  };

  const handleStopMonitoring = async () => {
    setLoadingMonitor(true);
    try {
      await axios.post(`${API}/monitor/stop`);
      toast.success("Folder monitoring stopped");
      await loadMonitorStatus();
    } catch (error) {
      console.error("Error stopping monitor:", error);
      toast.error("Failed to stop monitoring");
    } finally {
      setLoadingMonitor(false);
    }
  };

  const handleAddFolder = async () => {
    if (!newFolderPath.trim()) {
      toast.error("Please enter a folder path");
      return;
    }

    setLoadingMonitor(true);
    try {
      await axios.post(`${API}/monitor/add-folder`, {
        folder_path: newFolderPath.trim()
      });
      toast.success("Folder added successfully");
      // Don't clear the path - keep it for convenience
      // setNewFolderPath("");
      
      // Save to localStorage for persistence
      localStorage.setItem('lastMonitorPath', newFolderPath.trim());
      
      await loadMonitorStatus();
    } catch (error) {
      console.error("Error adding folder:", error);
      toast.error(error.response?.data?.detail || "Failed to add folder");
    } finally {
      setLoadingMonitor(false);
    }
  };

  const handleRemoveFolder = async (folderPath) => {
    setLoadingMonitor(true);
    try {
      await axios.delete(`${API}/monitor/folder`, {
        data: { folder_path: folderPath }
      });
      toast.success("Folder removed");
      await loadMonitorStatus();
    } catch (error) {
      console.error("Error removing folder:", error);
      toast.error("Failed to remove folder");
    } finally {
      setLoadingMonitor(false);
    }
  };

  const handleScanFolder = async (folderPath) => {
    setLoadingMonitor(true);
    try {
      const response = await axios.post(`${API}/monitor/scan-folder`, {
        folder_path: folderPath
      });
      setScanResults(response.data.files_without_nfo || []);
      toast.success(`Found ${response.data.count} files without NFO`);
    } catch (error) {
      console.error("Error scanning folder:", error);
      toast.error("Failed to scan folder");
    } finally {
      setLoadingMonitor(false);
    }
  };

  const handleToggleAutoScrape = async (enabled) => {
    try {
      await axios.put(`${API}/monitor/config`, {
        auto_scrape_enabled: enabled
      });
      toast.success(`Auto-scraping ${enabled ? 'enabled' : 'disabled'}`);
      await loadMonitorStatus();
    } catch (error) {
      console.error("Error updating config:", error);
      toast.error("Failed to update configuration");
    }
  };

  // System info functions
  const loadSystemInfo = async () => {
    try {
      setLoadingSystemInfo(true);
      const response = await axios.get(`${API}/system/info`);
      setSystemInfo(response.data);
    } catch (error) {
      console.error("Error loading system info:", error);
      toast.error("Failed to load system information");
    } finally {
      setLoadingSystemInfo(false);
    }
  };

  const loadSystemLogs = async (service = 'all') => {
    try {
      const response = await axios.get(`${API}/system/logs`, {
        params: { lines: 50, service }
      });
      setSystemLogs(response.data.logs);
    } catch (error) {
      console.error("Error loading logs:", error);
      toast.error("Failed to load logs");
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const formatUptime = (seconds) => {
    if (!seconds) return '0s';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    let result = [];
    if (days > 0) result.push(`${days}d`);
    if (hours > 0) result.push(`${hours}h`);
    if (minutes > 0) result.push(`${minutes}m`);
    if (secs > 0) result.push(`${secs}s`);
    
    return result.join(' ') || '0s';
  };

  const restartBackend = async () => {
    try {
      setRestartingBackend(true);
      const response = await axios.post(`${API}/system/restart`);
      
      if (response.data.success) {
        toast.success("Backend wird neu gestartet. Bitte warten Sie 10-15 Sekunden...");
        
        // Wait a bit before reloading system info
        setTimeout(() => {
          loadSystemInfo();
          setRestartingBackend(false);
        }, 12000);
      }
    } catch (error) {
      console.error("Error restarting backend:", error);
      toast.error("Backend-Neustart fehlgeschlagen: " + (error.response?.data?.detail || error.message));
      setRestartingBackend(false);
    }
  };


  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900">
      <Toaster richColors position="top-right" />
      
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8 text-center">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Film className="w-12 h-12 text-purple-400" />
            <h1 className="text-4xl font-bold text-white">Emby Metadata Scraper</h1>
          </div>
          <p className="text-gray-300 text-lg">Scrape adult content metadata for Emby Media Server</p>
          <div className="flex items-center justify-center gap-2 mt-4">
            <Badge variant="secondary">Gay DVD Empire</Badge>
            <Badge variant="secondary">AEBN</Badge>
            <Badge variant="secondary">GEVI</Badge>
            <Badge variant="secondary">RadVideo</Badge>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-5 mb-8">
            <TabsTrigger value="scrape" data-testid="scrape-tab">
              <Film className="w-4 h-4 mr-2" />
              Scrape by ID
            </TabsTrigger>
            <TabsTrigger value="search" data-testid="search-tab">
              <Search className="w-4 h-4 mr-2" />
              Search
            </TabsTrigger>
            <TabsTrigger value="monitor" data-testid="monitor-tab">
              <FolderOpen className="w-4 h-4 mr-2" />
              Auto Monitor
            </TabsTrigger>
            <TabsTrigger value="history" data-testid="history-tab">
              <Database className="w-4 h-4 mr-2" />
              History
            </TabsTrigger>
            <TabsTrigger value="system" data-testid="system-tab">
              <Activity className="w-4 h-4 mr-2" />
              System Info
            </TabsTrigger>
          </TabsList>

          {/* Scrape by ID Tab */}
          <TabsContent value="scrape" data-testid="scrape-content">
            <Card className="bg-gray-800/50 border-purple-500/30">
              <CardHeader>
                <CardTitle className="text-white">Scrape Movie Metadata</CardTitle>
                <CardDescription className="text-gray-300">
                  Enter a movie ID to scrape metadata and generate NFO file
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-white">Source Website</label>
                  <Select value={source} onValueChange={setSource}>
                    <SelectTrigger className="bg-gray-700 border-purple-500/30 text-white" data-testid="source-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gaydvdempire">Gay DVD Empire</SelectItem>
                      <SelectItem value="aebn">AEBN</SelectItem>
                      <SelectItem value="gevi">GEVI</SelectItem>
                      <SelectItem value="radvideo">RadVideo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-white">Movie ID or URL</label>
                  <Input
                    data-testid="movie-id-input"
                    placeholder="e.g., 5026246 or https://www.gaydvdempire.com/5026246/"
                    value={movieId}
                    onChange={(e) => setMovieId(e.target.value)}
                    className="bg-gray-700 border-purple-500/30 text-white placeholder:text-gray-400"
                    onKeyPress={(e) => e.key === 'Enter' && handleScrape()}
                  />
                  <p className="text-xs text-gray-400">💡 Paste the full URL or just the ID - we'll figure it out!</p>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-white">Output Path (Optional)</label>
                  <Input
                    data-testid="output-path-input"
                    placeholder="e.g., C:\Movies\Film.mp4 or C:\Movies\ or U:\XXX 2\"
                    value={outputFilePath}
                    onChange={(e) => setOutputFilePath(e.target.value)}
                    className="bg-gray-700 border-purple-500/30 text-white placeholder:text-gray-400"
                  />
                  <p className="text-xs text-gray-400">
                    🖼️ Enter a folder path or full file path - poster will be downloaded automatically
                  </p>
                </div>

                <Button
                  data-testid="scrape-button"
                  onClick={handleScrape}
                  disabled={loading}
                  className="w-full bg-purple-600 hover:bg-purple-700"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Scraping...
                    </>
                  ) : (
                    <>Scrape Metadata</>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Metadata Display */}
            {metadata && (
              <Card className="mt-6 bg-gray-800/50 border-purple-500/30" data-testid="metadata-display">
                <CardHeader>
                  <CardTitle className="text-white">Scraped Metadata</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid md:grid-cols-3 gap-6">
                    {/* Poster */}
                    {metadata.poster_url && (
                      <div className="col-span-1">
                        <img
                          src={
                            metadata.poster_url.includes('gayeroticvideoindex.com')
                              ? `${backendUrl}/api/proxy/image?url=${encodeURIComponent(metadata.poster_url)}`
                              : metadata.poster_url
                          }
                          alt={metadata.title}
                          className="w-full rounded-lg shadow-lg"
                          onError={(e) => {
                            e.target.style.display = 'none';
                          }}
                        />
                      </div>
                    )}

                    {/* Details */}
                    <div className={`${metadata.poster_url ? 'col-span-2' : 'col-span-3'} space-y-4`}>
                      <div>
                        <h3 className="text-2xl font-bold text-white mb-2">{metadata.title}</h3>
                        {metadata.year && (
                          <p className="text-gray-400">Year: {metadata.year}</p>
                        )}
                        {metadata.release_date && (
                          <p className="text-gray-400">Released: {metadata.release_date}</p>
                        )}
                      </div>

                      {metadata.studio && (
                        <div>
                          <p className="text-sm font-medium text-purple-400">Studio</p>
                          <p className="text-white">{metadata.studio}</p>
                        </div>
                      )}

                      {metadata.director && (
                        <div>
                          <p className="text-sm font-medium text-purple-400">Director</p>
                          <p className="text-white">{metadata.director}</p>
                        </div>
                      )}

                      {metadata.runtime && (
                        <div>
                          <p className="text-sm font-medium text-purple-400">Runtime</p>
                          <p className="text-white">{metadata.runtime} minutes</p>
                        </div>
                      )}

                      {metadata.plot && (
                        <div>
                          <p className="text-sm font-medium text-purple-400">Plot</p>
                          <p className="text-gray-300">{metadata.plot}</p>
                        </div>
                      )}

                      {metadata.genres && metadata.genres.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-purple-400 mb-2">Genres</p>
                          <div className="flex flex-wrap gap-2">
                            {metadata.genres.map((genre, idx) => (
                              <Badge key={idx} variant="outline" className="bg-purple-600/20 text-purple-300 border-purple-500/30">
                                {genre}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {metadata.actors && metadata.actors.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-purple-400 mb-2">Cast</p>
                          <div className="flex flex-wrap gap-2">
                            {metadata.actors.slice(0, 10).map((actor, idx) => (
                              <Badge key={idx} variant="secondary" className="bg-gray-700 text-white">
                                {actor.name}
                              </Badge>
                            ))}
                            {metadata.actors.length > 10 && (
                              <Badge variant="secondary" className="bg-gray-700 text-white">
                                +{metadata.actors.length - 10} more
                              </Badge>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
                <CardFooter>
                  <Button
                    data-testid="download-nfo-button"
                    onClick={handleDownloadNFO}
                    className="w-full bg-green-600 hover:bg-green-700"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download NFO File
                  </Button>
                </CardFooter>
              </Card>
            )}

            {/* NFO Preview */}
            {nfoContent && (
              <Card className="mt-6 bg-gray-800/50 border-purple-500/30">
                <CardHeader>
                  <CardTitle className="text-white">NFO File Preview</CardTitle>
                  <CardDescription className="text-gray-300">
                    This file should be placed in the same folder as your movie file
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <pre className="bg-gray-900 p-4 rounded-lg overflow-x-auto text-sm text-green-400">
                    {nfoContent}
                  </pre>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Search Tab */}
          <TabsContent value="search" data-testid="search-content">
            <Card className="bg-gray-800/50 border-purple-500/30">
              <CardHeader>
                <CardTitle className="text-white">Search Movies</CardTitle>
                <CardDescription className="text-gray-300">
                  Search for movies across multiple sources. GEVI search is disabled - please scrape by ID directly.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-white">Source Website</label>
                  <Select value={source} onValueChange={setSource}>
                    <SelectTrigger className="bg-gray-700 border-purple-500/30 text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gaydvdempire">Gay DVD Empire</SelectItem>
                      <SelectItem value="aebn">AEBN</SelectItem>
                      <SelectItem value="gevi" disabled>GEVI (Search Disabled - Use Scrape by ID)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-white">Search Query</label>
                  <Input
                    data-testid="search-input"
                    placeholder="Enter movie title..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-gray-700 border-purple-500/30 text-white placeholder:text-gray-400"
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  />
                </div>

                <Button
                  data-testid="search-button"
                  onClick={handleSearch}
                  disabled={loading}
                  className="w-full bg-purple-600 hover:bg-purple-700"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4 mr-2" />
                      Search
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="mt-6 space-y-4" data-testid="search-results">
                <h3 className="text-xl font-bold text-white">Search Results</h3>
                {searchResults.map((result, idx) => (
                  <Card key={idx} className="bg-gray-800/50 border-purple-500/30 hover:border-purple-500 transition-colors cursor-pointer"
                    onClick={() => handleSelectSearchResult(result)}
                  >
                    <CardContent className="p-4">
                      <div className="flex justify-between items-center">
                        <div>
                          <h4 className="text-white font-medium">{result.title}</h4>
                          {result.id && (
                            <p className="text-sm text-gray-400">ID: {result.id}</p>
                          )}
                        </div>
                        <Button size="sm" variant="outline" className="border-purple-500/30">
                          Select
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Auto Monitor Tab */}
          <TabsContent value="monitor" data-testid="monitor-content">
            <div className="space-y-6">
              {/* Status Card */}
              <Card className="bg-gray-800/50 border-purple-500/30">
                <CardHeader>
                  <CardTitle className="text-white flex items-center justify-between">
                    <span>Folder Monitoring Status</span>
                    {monitorStatus?.is_running ? (
                      <Badge className="bg-green-600">Running</Badge>
                    ) : (
                      <Badge variant="secondary">Stopped</Badge>
                    )}
                  </CardTitle>
                  <CardDescription className="text-gray-300">
                    Automatically detect new video files and generate NFO files
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-4">
                    {!monitorStatus?.is_running ? (
                      <Button
                        onClick={handleStartMonitoring}
                        disabled={loadingMonitor || !monitorStatus?.watched_folders?.length}
                        className="bg-green-600 hover:bg-green-700"
                        data-testid="start-monitor-button"
                      >
                        {loadingMonitor ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <Play className="w-4 h-4 mr-2" />
                        )}
                        Start Monitoring
                      </Button>
                    ) : (
                      <Button
                        onClick={handleStopMonitoring}
                        disabled={loadingMonitor}
                        variant="destructive"
                        data-testid="stop-monitor-button"
                      >
                        {loadingMonitor ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <Pause className="w-4 h-4 mr-2" />
                        )}
                        Stop Monitoring
                      </Button>
                    )}
                  </div>

                  {monitorStatus && (
                    <div className="grid grid-cols-2 gap-4 p-4 bg-gray-900/50 rounded-lg">
                      <div>
                        <p className="text-sm text-gray-400">Watched Folders</p>
                        <p className="text-xl font-bold text-white">{monitorStatus.folder_count}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-400">Auto-Scrape</p>
                        <p className="text-xl font-bold text-white">
                          {monitorStatus.auto_scrape_enabled ? 'Enabled' : 'Disabled'}
                        </p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Add Folder Card */}
              <Card className="bg-gray-800/50 border-purple-500/30">
                <CardHeader>
                  <CardTitle className="text-white">Add Folder to Watch</CardTitle>
                  <CardDescription className="text-gray-300">
                    Enter the full path to your Emby movie folder (e.g., C:\Movies or /media/movies)
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-2">
                    <Input
                      data-testid="folder-path-input"
                      placeholder="e.g., C:\Users\Username\Videos\Movies"
                      value={newFolderPath}
                      onChange={(e) => setNewFolderPath(e.target.value)}
                      className="flex-1 bg-gray-700 border-purple-500/30 text-white placeholder:text-gray-400"
                      onKeyPress={(e) => e.key === 'Enter' && handleAddFolder()}
                    />
                    <Button
                      onClick={handleAddFolder}
                      disabled={loadingMonitor || !newFolderPath.trim()}
                      className="bg-purple-600 hover:bg-purple-700"
                      data-testid="add-folder-button"
                    >
                      {loadingMonitor ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Plus className="w-4 h-4 mr-2" />
                      )}
                      Add Folder
                    </Button>
                  </div>

                  <div className="text-sm text-gray-400 space-y-1">
                    <p><strong>Windows Example:</strong> C:\Users\YourName\Videos\Adult Movies</p>
                    <p><strong>Linux Example:</strong> /home/username/media/movies</p>
                  </div>
                </CardContent>
              </Card>

              {/* Scraper Selection */}
              {monitorStatus && (
                <Card className="bg-gray-800/50 border-purple-500/30">
                  <CardHeader>
                    <CardTitle className="text-white">Auto-Scraper Settings</CardTitle>
                    <CardDescription className="text-gray-300">
                      Choose which scraper to use for automatic metadata detection
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-white">Preferred Scraper</label>
                      <Select 
                        value={monitorStatus.preferred_source || 'gaydvdempire'} 
                        onValueChange={async (value) => {
                          try {
                            await axios.post(`${API}/monitor/config`, { preferred_source: value });
                            toast.success(`Scraper changed to: ${value}`);
                            await loadMonitorStatus();
                          } catch (error) {
                            console.error('Error updating scraper:', error);
                            toast.error('Failed to update scraper');
                          }
                        }}
                      >
                        <SelectTrigger className="bg-gray-700 border-purple-500/30 text-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="gaydvdempire">Gay DVD Empire</SelectItem>
                          <SelectItem value="aebn">AEBN</SelectItem>
                          <SelectItem value="gevi">GEVI</SelectItem>
                          <SelectItem value="radvideo">RadVideo</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-gray-400">
                        💡 This scraper will be used when new videos are detected automatically
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Watched Folders List */}
              {monitorStatus?.watched_folders && monitorStatus.watched_folders.length > 0 && (
                <Card className="bg-gray-800/50 border-purple-500/30">
                  <CardHeader>
                    <CardTitle className="text-white">Watched Folders</CardTitle>
                    <CardDescription className="text-gray-300">
                      These folders are being monitored for new video files
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {monitorStatus.watched_folders.map((folder, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg border border-purple-500/20"
                      >
                        <div className="flex items-center gap-3 flex-1">
                          <FolderOpen className="w-5 h-5 text-purple-400" />
                          <span className="text-white font-mono text-sm break-all">{folder}</span>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleScanFolder(folder)}
                            className="border-purple-500/30"
                          >
                            <Eye className="w-4 h-4 mr-1" />
                            Scan
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleRemoveFolder(folder)}
                            data-testid={`remove-folder-${idx}`}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* Scan Results */}
              {scanResults.length > 0 && (
                <Card className="bg-gray-800/50 border-purple-500/30">
                  <CardHeader>
                    <CardTitle className="text-white">Scan Results</CardTitle>
                    <CardDescription className="text-gray-300">
                      Found {scanResults.length} video files without NFO files
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {scanResults.map((file, idx) => (
                        <div key={idx} className="p-3 bg-gray-700/50 rounded text-white text-sm font-mono">
                          {file}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Recently Processed Files */}
              {processedFiles.length > 0 && (
                <Card className="bg-gray-800/50 border-purple-500/30">
                  <CardHeader>
                    <CardTitle className="text-white">Recently Processed Files</CardTitle>
                    <CardDescription className="text-gray-300">
                      Files that were automatically processed by the monitor
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3 max-h-96 overflow-y-auto">
                      {processedFiles.slice(0, 10).map((file, idx) => (
                        <div
                          key={idx}
                          className="p-4 bg-gray-700/50 rounded-lg border border-purple-500/20"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <p className="text-white font-medium">{file.title || 'Unknown'}</p>
                              <p className="text-sm text-gray-400 font-mono mt-1">{file.file_path}</p>
                            </div>
                            <Badge
                              variant={file.status === 'success' ? 'default' : 'destructive'}
                              className={file.status === 'success' ? 'bg-green-600' : ''}
                            >
                              {file.status}
                            </Badge>
                          </div>
                          {file.nfo_path && (
                            <p className="text-xs text-gray-500 mt-2">NFO: {file.nfo_path}</p>
                          )}
                          {file.error && (
                            <p className="text-xs text-red-400 mt-2">Error: {file.error}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* How It Works */}
              <Card className="bg-gray-800/50 border-purple-500/30">
                <CardHeader>
                  <CardTitle className="text-white">How Auto-Monitoring Works</CardTitle>
                </CardHeader>
                <CardContent className="text-gray-300 space-y-2">
                  <p><strong className="text-purple-400">1. Add Folders:</strong> Add one or more folders where you store your movie files</p>
                  <p><strong className="text-purple-400">2. Start Monitoring:</strong> Click "Start Monitoring" to begin watching for new files</p>
                  <p><strong className="text-purple-400">3. Automatic Detection:</strong> When you add a new video file, it's automatically detected</p>
                  <p><strong className="text-purple-400">4. Smart Title Extraction:</strong> The app extracts the movie title from the filename</p>
                  <p><strong className="text-purple-400">5. Auto Search & Scrape:</strong> It searches GEVI, finds the best match, and scrapes metadata</p>
                  <p><strong className="text-purple-400">6. NFO Generation:</strong> An NFO file is created automatically in the same folder</p>
                  <p><strong className="text-purple-400">7. Emby Detection:</strong> Emby detects the new file and reads the NFO automatically</p>
                  
                  <div className="mt-4 p-4 bg-blue-900/20 border border-blue-500/30 rounded-lg">
                    <p className="text-sm"><strong>💡 Tip:</strong> For best results, name your files like: <code className="text-purple-300">"Movie Title (2023).mp4"</code> or <code className="text-purple-300">"Movie.Title.2023.1080p.mp4"</code></p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* History Tab */}
          <TabsContent value="history" data-testid="history-content">
            <Card className="bg-gray-800/50 border-purple-500/30">
              <CardHeader>
                <CardTitle className="text-white">Scraped Movies History</CardTitle>
                <CardDescription className="text-gray-300">
                  All movies you've scraped are saved here
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingMovies ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
                  </div>
                ) : savedMovies.length === 0 ? (
                  <div className="text-center py-8 text-gray-400">
                    <Database className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No movies scraped yet</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {savedMovies.map((movie) => (
                      <Card key={movie.id} className="bg-gray-700/50 border-purple-500/20">
                        <CardContent className="p-4">
                          <div className="flex gap-4">
                            {movie.poster_url && (
                              <img
                                src={movie.poster_url}
                                alt={movie.title}
                                className="w-24 h-36 object-cover rounded"
                                onError={(e) => {
                                  e.target.style.display = 'none';
                                }}
                              />
                            )}
                            <div className="flex-1">
                              <div className="flex justify-between items-start">
                                <div>
                                  <h4 className="text-white font-bold text-lg">{movie.title}</h4>
                                  <div className="flex items-center gap-2 mt-1">
                                    <Badge variant="outline" className="text-xs">
                                      {movie.source}
                                    </Badge>
                                    {movie.year && (
                                      <span className="text-sm text-gray-400">{movie.year}</span>
                                    )}
                                  </div>
                                </div>
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  onClick={() => handleDeleteMovie(movie.id)}
                                  data-testid={`delete-movie-${movie.id}`}
                                >
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </div>
                              
                              {movie.studio && (
                                <p className="text-sm text-gray-300 mt-2">Studio: {movie.studio}</p>
                              )}
                              
                              {movie.plot && (
                                <p className="text-sm text-gray-400 mt-2 line-clamp-2">{movie.plot}</p>
                              )}
                              
                              {movie.genres && movie.genres.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {movie.genres.slice(0, 3).map((genre, idx) => (
                                    <Badge key={idx} variant="secondary" className="text-xs">
                                      {genre}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* System Info Tab */}
          <TabsContent value="system" data-testid="system-content">
            <div className="space-y-6">
              {/* Load System Info Button */}
              <Card className="bg-gray-800/50 border-purple-500/30">
                <CardContent className="p-6">
                  <Button 
                    onClick={() => {
                      loadSystemInfo();
                      loadSystemLogs('all');
                    }}
                    disabled={loadingSystemInfo}
                    className="w-full"
                  >
                    {loadingSystemInfo ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Loading System Info...
                      </>
                    ) : (
                      <>
                        <Activity className="w-4 h-4 mr-2" />
                        Refresh System Info
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>

              {systemInfo && (
                <>
                  {/* System Overview */}
                  <Card className="bg-gray-800/50 border-purple-500/30">
                    <CardHeader>
                      <CardTitle className="text-white">System Overview</CardTitle>
                      <CardDescription className="text-gray-300">
                        Current system status and resource usage
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-gray-700/50 p-4 rounded-lg">
                          <p className="text-sm text-gray-400 mb-1">Platform</p>
                          <p className="text-white font-semibold">{systemInfo.platform.system} {systemInfo.platform.release}</p>
                        </div>
                        <div className="bg-gray-700/50 p-4 rounded-lg">
                          <p className="text-sm text-gray-400 mb-1">Python Version</p>
                          <p className="text-white font-semibold">{systemInfo.platform.python_version}</p>
                        </div>
                        <div className="bg-gray-700/50 p-4 rounded-lg">
                          <p className="text-sm text-gray-400 mb-1">CPU Usage</p>
                          <p className="text-white font-semibold">{systemInfo.resources.cpu_percent}% ({systemInfo.resources.cpu_count} cores)</p>
                        </div>
                        <div className="bg-gray-700/50 p-4 rounded-lg">
                          <p className="text-sm text-gray-400 mb-1">Memory Usage</p>
                          <p className="text-white font-semibold">{systemInfo.resources.memory.percent}% ({formatBytes(systemInfo.resources.memory.used)} / {formatBytes(systemInfo.resources.memory.total)})</p>
                        </div>
                        <div className="bg-gray-700/50 p-4 rounded-lg">
                          <p className="text-sm text-gray-400 mb-1">Disk Usage</p>
                          <p className="text-white font-semibold">{systemInfo.resources.disk.percent}% ({formatBytes(systemInfo.resources.disk.used)} / {formatBytes(systemInfo.resources.disk.total)})</p>
                        </div>
                        <div className="bg-gray-700/50 p-4 rounded-lg">
                          <p className="text-sm text-gray-400 mb-1">Backend Uptime</p>
                          <p className="text-white font-semibold">{formatUptime(systemInfo.backend.uptime_seconds)}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Backend Service */}
                  <Card className="bg-gray-800/50 border-purple-500/30">
                    <CardHeader>
                      <CardTitle className="text-white">Backend Service</CardTitle>
                      <CardDescription className="text-gray-300">
                        Backend process information
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex justify-between items-center py-2 border-b border-gray-700">
                        <span className="text-gray-400">Process ID</span>
                        <Badge variant="outline">{systemInfo.backend.pid}</Badge>
                      </div>
                      <div className="flex justify-between items-center py-2 border-b border-gray-700">
                        <span className="text-gray-400">CPU Usage</span>
                        <span className="text-white">{systemInfo.backend.cpu_percent}%</span>
                      </div>
                      <div className="flex justify-between items-center py-2 border-b border-gray-700">
                        <span className="text-gray-400">Memory Usage</span>
                        <span className="text-white">{systemInfo.backend.memory_mb.toFixed(2)} MB</span>
                      </div>
                      <div className="flex justify-between items-center py-2 border-b border-gray-700">
                        <span className="text-gray-400">Threads</span>
                        <span className="text-white">{systemInfo.backend.threads}</span>
                      </div>
                      <div className="mt-4 pt-4 border-t border-gray-700">
                        <Button 
                          onClick={restartBackend}
                          variant="destructive"
                          className="w-full"
                          disabled={restartingBackend}
                        >
                          {restartingBackend ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Backend wird neugestartet...
                            </>
                          ) : (
                            <>
                              <Activity className="w-4 h-4 mr-2" />
                              Backend neu starten
                            </>
                          )}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Scrapers */}
                  <Card className="bg-gray-800/50 border-purple-500/30">
                    <CardHeader>
                      <CardTitle className="text-white">Available Scrapers</CardTitle>
                      <CardDescription className="text-gray-300">
                        {systemInfo.scrapers.total} scrapers ready
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-2">
                        {systemInfo.scrapers.available.map((scraper, idx) => (
                          <Badge key={idx} variant="secondary" className="capitalize">
                            {scraper}
                          </Badge>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Logs */}
                  {(systemLogs.backend || systemLogs.frontend) && (
                    <Card className="bg-gray-800/50 border-purple-500/30">
                      <CardHeader>
                        <CardTitle className="text-white">System Logs</CardTitle>
                        <CardDescription className="text-gray-300">
                          Recent log entries from services
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {systemLogs.backend && (
                          <div>
                            <h4 className="text-white font-semibold mb-2">Backend Logs</h4>
                            <div className="bg-gray-900 p-4 rounded-lg overflow-x-auto">
                              <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">
                                {systemLogs.backend}
                              </pre>
                            </div>
                          </div>
                        )}
                        {systemLogs.frontend && (
                          <div>
                            <h4 className="text-white font-semibold mb-2">Frontend Logs</h4>
                            <div className="bg-gray-900 p-4 rounded-lg overflow-x-auto">
                              <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">
                                {systemLogs.frontend}
                              </pre>
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )}
                </>
              )}

              {!systemInfo && !loadingSystemInfo && (
                <Card className="bg-gray-800/50 border-purple-500/30">
                  <CardContent className="p-12 text-center">
                    <Activity className="w-16 h-16 mx-auto mb-4 text-gray-500" />
                    <p className="text-gray-400">Click "Refresh System Info" to load system information</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* Instructions Card */}
        <Card className="mt-8 bg-gray-800/50 border-purple-500/30">
          <CardHeader>
            <CardTitle className="text-white">How to Use</CardTitle>
          </CardHeader>
          <CardContent className="text-gray-300 space-y-2">
            <p><strong className="text-purple-400">1. Scrape by ID:</strong> Enter a movie ID from Gay DVD Empire, AEBN, or GEVI to fetch metadata</p>
            <p><strong className="text-purple-400">2. Search:</strong> Search for movies on GEVI and select one to scrape</p>
            <p><strong className="text-purple-400">3. Download NFO:</strong> After scraping, download the NFO file</p>
            <p><strong className="text-purple-400">4. Install in Emby:</strong> Place the .nfo file in the same folder as your movie file with the same name</p>
            <p className="text-sm text-gray-500 mt-4">Example: If your movie is "movie.mp4", save the NFO as "movie.nfo"</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default App;