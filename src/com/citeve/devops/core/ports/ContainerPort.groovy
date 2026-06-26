package com.citeve.devops.core.ports

import com.citeve.devops.core.model.Component

interface ContainerPort {
    void startContainer(Component component, String network)
    void stopContainer(Component component)
    void restartContainer(Component component)
    void buildContainer(Component component)
    boolean isContainerHealthy(Component component)
    String getContainerStatus(Component component)
}