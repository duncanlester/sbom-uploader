#!/usr/bin/env groovy

/**
 * Fetch all projects from Dependency-Track with pagination.
 *
 * DT caps results at 100 per page regardless of the requested pageSize,
 * so this helper paginates through all pages and returns the full list.
 *
 * @param dtUrl  Dependency-Track API base URL
 * @return       List of all project maps from the DT API
 */

def call(String dtUrl = 'http://w-work-19.rdmz.isridev.com:8081') {
    def allProjects = []
    def pageNumber = 1
    def keepGoing = true

    while (keepGoing) {
        def pageJson = sh(script: """
            curl -s -X GET '${dtUrl}/api/v1/project?pageSize=100&pageNumber=${pageNumber}' \
                -H "X-Api-Key: \$DT_API_KEY"
        """, returnStdout: true).trim()

        if (!pageJson || pageJson == '[]' || pageJson == 'null') {
            keepGoing = false
        } else {
            def page = readJSON text: pageJson
            if (page instanceof List && page.size() > 0) {
                allProjects.addAll(page)
                keepGoing = (page.size() >= 100)
                pageNumber++
            } else {
                keepGoing = false
            }
        }
    }

    echo "Fetched ${allProjects.size()} projects from Dependency-Track (${pageNumber - 1} page(s))"
    return allProjects
}
