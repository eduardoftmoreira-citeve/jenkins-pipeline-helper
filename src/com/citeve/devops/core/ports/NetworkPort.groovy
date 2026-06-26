package com.citeve.devops.core.ports

interface NetworkPort {
    void createNetwork(String name)
    void deleteNetwork(String name)
    boolean networkExists(String name)
    void connectToNetwork(String network, String container)
}