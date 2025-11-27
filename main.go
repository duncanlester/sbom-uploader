package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/go-git/go-git/v5"
	"github.com/go-resty/resty/v2"
	"gopkg.in/yaml.v3"
)

type Config struct {
	NodeRepoURL             string `yaml:"node_repo_url"`
	SbomFile                string `yaml:"sbom_file"`
	DependencyTrackAPIURL   string `yaml:"dependency_track_api_url"`
	DependencyTrackAPIKey   string `yaml:"dependency_track_api_key"`
	ProjectName             string `yaml:"project_name"`
	ProjectVersion          string `yaml:"project_version"`
	ReportFile              string `yaml:"report_file"`
}

func readConfig(filename string) (*Config, error) {
	data, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	cfg := &Config{}
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}

func checkoutNodeApp(repoURL string, workDir string) error {
	log.Println("Cloning Node.js repo:", repoURL)
	_, err := git.PlainClone(workDir, false, &git.CloneOptions{
		URL:      repoURL,
		Progress: os.Stdout,
	})
	return err
}

func generateSBOM(appDir, outputFile string) error {
	log.Println("Generating SBOM (CycloneDX Go calls npm package)")
	// Uses CycloneDX Node.js CLI: npx @cyclonedx/bom
	cmd := exec.Command("npx", "@cyclonedx/bom", "-o", outputFile)
	cmd.Dir = appDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func uploadSBOMToDT(cfg *Config, sbomPath string) (string, error) {
	log.Println("Uploading SBOM to Dependency-Track...")

	sbomData, err := ioutil.ReadFile(sbomPath)
	if err != nil {
		return "", err
	}

	client := resty.New()
	resp, err := client.R().
		SetHeader("X-Api-Key", cfg.DependencyTrackAPIKey).
		SetFileReader("bom", sbomPath, bytes.NewReader(sbomData)).
		SetFormData(map[string]string{
			"projectName":    cfg.ProjectName,
			"projectVersion": cfg.ProjectVersion,
			"autoCreate":     "true",
		}).
		Post(cfg.DependencyTrackAPIURL + "/bom")
	if err != nil {
		return "", err
	}
	if resp.StatusCode() >= 300 {
		return "", fmt.Errorf("Dependency-Track upload failed: %s", resp.String())
	}

	// Get Project UUID (search DT for project)
	var projectUUID string
	resp2, err := client.R().
		SetHeader("X-Api-Key", cfg.DependencyTrackAPIKey).
		SetQueryParams(map[string]string{
			"name":    cfg.ProjectName,
			"version": cfg.ProjectVersion,
		}).
		Get(cfg.DependencyTrackAPIURL + "/project")
	if err != nil {
		return "", err
	}
	var projects []map[string]interface{}
	if err := json.Unmarshal(resp2.Body(), &projects); err != nil {
		return "", err
	}
	if len(projects) > 0 && projects[0]["uuid"] != nil {
		projectUUID, _ = projects[0]["uuid"].(string)
	}
	if projectUUID == "" {
		return "", fmt.Errorf("No project UUID found for %s/%s", cfg.ProjectName, cfg.ProjectVersion)
	}
	return projectUUID, nil
}

func renderReport(reportPath string, cfg *Config, projectUUID string) error {
	const tmplPath = "templates/report.html.tmpl"
	tmplBytes, err := ioutil.ReadFile(tmplPath)
	if err != nil {
		return err
	}
	tmpl := template.Must(template.New("report").Parse(string(tmplBytes)))
	link := fmt.Sprintf("%s/project/%s", cfg.DependencyTrackAPIURL[:len(cfg.DependencyTrackAPIURL)-7], projectUUID) // strips "/api/v1"
	f, err := os.Create(reportPath)
	if err != nil {
		return err
	}
	defer f.Close()
	data := struct {
		ProjectName string
		ProjectVersion string
		DTProjectLink string
	}{
		cfg.ProjectName,
		cfg.ProjectVersion,
		link,
	}
	return tmpl.Execute(f, data)
}

func main() {
	cfg, err := readConfig("config.yaml")
	if err != nil {
		log.Fatalf("Error reading config: %v", err)
	}
	workDir, _ := ioutil.TempDir("", "node-app")
	defer os.RemoveAll(workDir)
	// 1. Clone repo
	if err := checkoutNodeApp(cfg.NodeRepoURL, workDir); err != nil {
		log.Fatalf("Clone failed: %v", err)
	}
	// 2. Generate SBOM
	sbomPath := filepath.Join(workDir, cfg.SbomFile)
	if err := generateSBOM(workDir, sbomPath); err != nil {
		log.Fatalf("SBOM gen failed: %v", err)
	}
	// 3. Upload SBOM to Dependency-Track
	projUUID, err := uploadSBOMToDT(cfg, sbomPath)
	if err != nil {
		log.Fatalf("Dependency-Track upload failed: %v", err)
	}
	// 4. Write HTML report
	if err := renderReport(cfg.ReportFile, cfg, projUUID); err != nil {
		log.Fatalf("HTML report failed: %v", err)
	}
	fmt.Println("Done! Report:", cfg.ReportFile)
}