package main

import (
	"log"
	"net/http"
	"github.com/gin-gonic/gin"
)

func main() {
	// Disable console color and debug logs.
	gin.SetMode(gin.ReleaseMode)

	router := gin.New()

	router.GET("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"message": "Hello, World!",
		})
	})

	// Run the server on 0.0.0.0:8000.
	log.Println("Starting Gin server on :8000...")
	if err := router.Run(":8000"); err != nil {
		log.Fatal("Server failed to run: ", err)
	}
}